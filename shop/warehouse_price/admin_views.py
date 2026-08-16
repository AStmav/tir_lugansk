import os
import tempfile
import traceback

from django.conf import settings
from django.contrib import admin, messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils import timezone

from shop.forms.warehouse_price_form import WarehousePriceUploadForm
from shop.models import Warehouse, WarehousePriceImport
from shop.warehouse_price.error_report import format_reasons_summary, preview_error_log
from shop.warehouse_price.parser import preview_headers
from shop.warehouse_price.presets import match_preset_key, presets_for_js, settings_to_form_initial
from shop.utils.price_import_runner import (
    launch_price_import_subprocess,
    warehouse_has_running_price_import,
)


class WarehousePriceImportInline(admin.TabularInline):
    model = WarehousePriceImport
    extra = 0
    can_delete = False
    max_num = 10
    readonly_fields = [
        'original_filename',
        'status',
        'processed_rows',
        'total_rows',
        'updated_rows',
        'skipped_rows',
        'error_count',
        'import_report_link',
        'created_at',
        'processed_at',
    ]
    fields = readonly_fields
    verbose_name = 'Загрузка прайса'
    verbose_name_plural = 'История загрузок прайса'

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description='Отчёт')
    def import_report_link(self, obj: WarehousePriceImport):
        if not obj.pk:
            return '—'
        url = reverse('admin:shop_warehousepriceimport_change', args=[obj.pk])
        if obj.error_count:
            label = f'Ошибки ({obj.error_count})'
        elif obj.status == WarehousePriceImport.STATUS_FAILED:
            label = 'Сбой импорта'
        else:
            label = 'Детали'
        return format_html('<a href="{}">{}</a>', url, label)


class WarehousePriceImportAdminMixin:
    """Кнопка «Загрузить прайс» на странице склада."""

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<path:object_id>/upload-price/',
                self.admin_site.admin_view(self.upload_price_view),
                name='shop_warehouse_upload_price',
            ),
        ]
        return custom + urls

    def upload_price_view(self, request, object_id):
        warehouse = get_object_or_404(Warehouse, pk=object_id)
        initial = _initial_from_warehouse(warehouse)

        if request.method == 'POST':
            form = WarehousePriceUploadForm(request.POST, request.FILES)
            if form.is_valid():
                return self._process_upload(request, warehouse, form)
        else:
            form = WarehousePriceUploadForm(initial=initial)

        preview = []
        if request.method == 'POST' and request.FILES.get('file'):
            try:
                preview = _preview_file(request.FILES['file'], form.data.get('header_row') or 1)
            except Exception as exc:
                messages.warning(request, f'Не удалось прочитать превью: {exc}')

        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'original': warehouse,
            'form': form,
            'title': f'Загрузка прайса: {warehouse.name_internal}',
            'preview_headers': preview,
            'presets_json': presets_for_js(),
            'import_in_progress': warehouse_has_running_price_import(warehouse.pk),
        }
        return render(request, 'admin/shop/warehouse/upload_price.html', context)

    def _process_upload(self, request, warehouse, form):
        if warehouse_has_running_price_import(warehouse.pk):
            messages.error(
                request,
                'У этого склада уже выполняется импорт прайса. '
                'Дождитесь завершения или откройте запись в истории загрузок.',
            )
            return redirect(reverse('admin:shop_warehouse_change', args=[warehouse.pk]))

        upload = form.cleaned_data['file']
        settings_payload = form.build_import_settings()

        price_import = WarehousePriceImport.objects.create(
            warehouse=warehouse,
            file=upload,
            original_filename=getattr(upload, 'name', ''),
            status=WarehousePriceImport.STATUS_PENDING,
            import_settings=settings_payload,
            uploaded_by=request.user if request.user.is_authenticated else None,
        )

        if form.cleaned_data.get('save_mapping'):
            warehouse.import_settings = settings_payload
            warehouse.save(update_fields=['import_settings', 'updated_at'])

        report_url = reverse('admin:shop_warehousepriceimport_change', args=[price_import.pk])
        try:
            pid, log_path = launch_price_import_subprocess(price_import.pk)
        except Exception as exc:
            price_import.refresh_from_db()
            if price_import.status != WarehousePriceImport.STATUS_FAILED:
                price_import.status = WarehousePriceImport.STATUS_FAILED
                price_import.summary = str(exc)
                price_import.error_log = traceback.format_exc()
                price_import.processed_at = timezone.now()
                price_import.save()
            messages.error(
                request,
                format_html(
                    'Не удалось запустить импорт: {}. <a href="{}">Подробности</a>',
                    exc,
                    report_url,
                ),
            )
            return redirect(report_url)

        rel_log = os.path.relpath(log_path, settings.BASE_DIR)
        messages.success(
            request,
            format_html(
                'Файл принят. Импорт запущен в фоне (PID {}). '
                'Страница обновляется автоматически, пока идёт обработка. '
                '<a href="{}">Статус импорта</a>. Лог: {}',
                pid,
                report_url,
                rel_log,
            ),
        )
        return redirect(report_url)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['upload_price_url'] = reverse(
            'admin:shop_warehouse_upload_price',
            args=[object_id],
        )
        return super().change_view(request, object_id, form_url, extra_context)


def _initial_from_warehouse(warehouse: Warehouse) -> dict:
    settings = warehouse.import_settings or {}
    initial = settings_to_form_initial(settings)
    initial['preset'] = match_preset_key(settings)
    return initial


def _preview_file(uploaded_file, header_row) -> list:
    header_row = int(header_row or 1)
    suffix = os.path.splitext(uploaded_file.name)[1] or '.csv'
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        for chunk in uploaded_file.chunks():
            tmp.write(chunk)
        path = tmp.name
    try:
        return preview_headers(path, header_row)
    finally:
        os.unlink(path)


@admin.register(WarehousePriceImport)
class WarehousePriceImportAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'warehouse',
        'original_filename',
        'status',
        'processed_rows',
        'total_rows',
        'updated_rows',
        'skipped_rows',
        'error_count',
        'created_at',
        'import_report_link',
    ]
    list_filter = ['status', 'warehouse']
    search_fields = ['original_filename', 'warehouse__name_internal', 'warehouse__name_public']
    readonly_fields = [
        'warehouse',
        'file',
        'original_filename',
        'status',
        'import_progress',
        'total_rows',
        'processed_rows',
        'updated_rows',
        'skipped_rows',
        'error_count',
        'summary',
        'skip_reasons_summary',
        'error_log_actions',
        'error_log_preview',
        'error_log',
        'uploaded_by',
        'created_at',
        'started_at',
        'processed_at',
    ]
    fieldsets = (
        (None, {
            'fields': (
                'warehouse',
                'original_filename',
                'file',
                'status',
                'import_progress',
                'uploaded_by',
                'created_at',
                'started_at',
                'processed_at',
            ),
        }),
        ('Результат', {
            'fields': (
                'total_rows',
                'processed_rows',
                'updated_rows',
                'skipped_rows',
                'error_count',
                'summary',
            ),
        }),
        ('Отчёт о пропущенных строках', {
            'fields': (
                'skip_reasons_summary',
                'error_log_actions',
                'error_log_preview',
                'error_log',
            ),
            'description': (
                'Строки прайса, которые не удалось сопоставить с товаром на сайте '
                '(номер строки, артикул, бренд, причина).'
            ),
        }),
    )

    def has_add_permission(self, request):
        return False

    change_form_template = 'admin/shop/warehousepriceimport/change_form.html'

    @admin.display(description='Прогресс')
    def import_progress(self, obj: WarehousePriceImport):
        if obj.status == WarehousePriceImport.STATUS_PROCESSING:
            if obj.total_rows:
                pct = int(obj.processed_rows * 100 / obj.total_rows)
                text = f'{obj.processed_rows:,} / {obj.total_rows:,} ({pct}%)'.replace(',', ' ')
            else:
                text = f'Обработано строк: {obj.processed_rows:,}'.replace(',', ' ')
            return format_html(
                '<strong style="color:#0066cc;">{}</strong> '
                '<span class="help">— страница обновляется каждые 15 сек.</span>',
                text,
            )
        if obj.status == WarehousePriceImport.STATUS_COMPLETED and obj.total_rows:
            return f'{obj.processed_rows} / {obj.total_rows}'
        if obj.processed_rows:
            return str(obj.processed_rows)
        return '—'

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<path:object_id>/download-errors/',
                self.admin_site.admin_view(self.download_errors_view),
                name='shop_warehousepriceimport_download_errors',
            ),
        ]
        return custom + urls

    @admin.display(description='Отчёт')
    def import_report_link(self, obj: WarehousePriceImport):
        if not obj.pk:
            return '—'
        url = reverse('admin:shop_warehousepriceimport_change', args=[obj.pk])
        if obj.error_count:
            return format_html('<a href="{}">Ошибки ({})</a>', url, obj.error_count)
        return format_html('<a href="{}">Открыть</a>', url)

    @admin.display(description='Причины пропуска (сводка)')
    def skip_reasons_summary(self, obj: WarehousePriceImport):
        text = format_reasons_summary(obj.error_log or '')
        return format_html('<pre style="margin:0; white-space:pre-wrap;">{}</pre>', text)

    @admin.display(description='Действия')
    def error_log_actions(self, obj: WarehousePriceImport):
        if not obj.pk or not (obj.error_log or '').strip():
            return '—'
        download_url = reverse(
            'admin:shop_warehousepriceimport_download_errors',
            args=[obj.pk],
        )
        warehouse_url = reverse('admin:shop_warehouse_change', args=[obj.warehouse_id])
        return format_html(
            '<a class="button" href="{}">Скачать CSV с ошибками</a> '
            '&nbsp; <a href="{}">← К складу</a>',
            download_url,
            warehouse_url,
        )

    @admin.display(description='Пропущенные строки (превью)')
    def error_log_preview(self, obj: WarehousePriceImport):
        preview = preview_error_log(obj.error_log or '')
        if not preview:
            return '—'
        return format_html(
            '<pre style="max-height:420px; overflow:auto; margin:0; font-size:12px;">{}</pre>',
            preview,
        )

    def download_errors_view(self, request, object_id):
        price_import = get_object_or_404(WarehousePriceImport, pk=object_id)
        content = price_import.error_log or 'row;article;brand;reason\n'
        filename = f'price_import_{price_import.pk}_errors.csv'
        if price_import.original_filename:
            base = os.path.splitext(price_import.original_filename)[0]
            # ASCII-имя файла для совместимости с Content-Disposition
            safe_base = ''.join(ch if ch.isascii() and ch not in '"\\' else '_' for ch in base)
            safe_base = safe_base.strip('._') or f'import_{price_import.pk}'
            filename = f'{safe_base}_errors.csv'
        response = HttpResponse(content, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
