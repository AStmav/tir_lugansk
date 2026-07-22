import os
import tempfile
import traceback

from django.contrib import admin, messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils import timezone

from shop.forms.warehouse_price_form import WarehousePriceUploadForm
from shop.models import Warehouse, WarehousePriceImport
from shop.warehouse_price.parser import preview_headers
from shop.warehouse_price.presets import match_preset_key, presets_for_js, settings_to_form_initial
from shop.warehouse_price.service import run_warehouse_price_import


class WarehousePriceImportInline(admin.TabularInline):
    model = WarehousePriceImport
    extra = 0
    can_delete = False
    max_num = 10
    readonly_fields = [
        'original_filename',
        'status',
        'total_rows',
        'updated_rows',
        'skipped_rows',
        'error_count',
        'created_at',
        'processed_at',
    ]
    fields = readonly_fields
    verbose_name = 'Загрузка прайса'
    verbose_name_plural = 'История загрузок прайса'

    def has_add_permission(self, request, obj=None):
        return False


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
        }
        return render(request, 'admin/shop/warehouse/upload_price.html', context)

    def _process_upload(self, request, warehouse, form):
        upload = form.cleaned_data['file']
        settings = form.build_import_settings()

        price_import = WarehousePriceImport.objects.create(
            warehouse=warehouse,
            file=upload,
            original_filename=getattr(upload, 'name', ''),
            status=WarehousePriceImport.STATUS_PROCESSING,
            uploaded_by=request.user if request.user.is_authenticated else None,
        )

        if form.cleaned_data.get('save_mapping'):
            warehouse.import_settings = settings
            warehouse.save(update_fields=['import_settings', 'updated_at'])

        file_path = price_import.file.path
        try:
            from django.db import transaction

            with transaction.atomic():
                stats = run_warehouse_price_import(
                    warehouse=warehouse,
                    file_path=file_path,
                    import_settings=settings,
                    price_import=price_import,
                )
            messages.success(
                request,
                f'Прайс обработан: обновлено {stats.updated}, пропущено {stats.skipped} '
                f'из {stats.total} строк.',
            )
            if stats.errors:
                messages.warning(
                    request,
                    f'Есть пропущенные строки ({len(stats.errors)}). Смотрите лог в истории импорта.',
                )
        except Exception as exc:
            price_import.status = WarehousePriceImport.STATUS_FAILED
            price_import.summary = str(exc)
            price_import.error_log = traceback.format_exc()
            price_import.processed_at = timezone.now()
            price_import.save()
            messages.error(request, f'Ошибка импорта: {exc}')
            return redirect(
                reverse('admin:shop_warehouse_upload_price', args=[warehouse.pk])
            )

        return redirect(reverse('admin:shop_warehouse_change', args=[warehouse.pk]))

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
        'updated_rows',
        'skipped_rows',
        'created_at',
    ]
    list_filter = ['status', 'warehouse']
    readonly_fields = [
        'warehouse',
        'file',
        'original_filename',
        'status',
        'total_rows',
        'updated_rows',
        'skipped_rows',
        'error_count',
        'summary',
        'error_log',
        'uploaded_by',
        'created_at',
        'processed_at',
    ]

    def has_add_permission(self, request):
        return False
