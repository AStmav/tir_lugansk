from django import forms

from shop.models import Brand
from shop.warehouse_price.presets import (
    PRESET_CUSTOM,
    get_preset_settings,
    preset_choices,
    settings_to_form_initial,
)


class WarehousePriceUploadForm(forms.Form):
    preset = forms.ChoiceField(
        label='Шаблон прайса',
        choices=preset_choices,
        initial=PRESET_CUSTOM,
        required=True,
        help_text=(
            'Выберите готовый формат поставщика — поля ниже заполнятся сами. '
            '«Свой» — ручной маппинг или сохранённые настройки склада.'
        ),
    )
    file = forms.FileField(label='Файл прайса (.xlsx или .csv)')
    header_row = forms.IntegerField(
        label='Строка заголовков',
        min_value=1,
        initial=1,
    )
    data_start_row = forms.IntegerField(
        label='Первая строка данных',
        min_value=1,
        initial=2,
    )
    col_article = forms.CharField(
        label='Колонка артикула',
        help_text='Заголовок колонки, буква (A) или номер (0)',
        required=False,
    )
    col_brand = forms.CharField(
        label='Колонка бренда',
        required=False,
        help_text='Необязательно, если выбран фиксированный бренд',
    )
    col_price = forms.CharField(label='Колонка цены', required=False)
    col_qty = forms.CharField(label='Колонка остатка', required=False)
    col_external_id = forms.CharField(
        label='Колонка кода 1С (Код ID)',
        required=False,
    )
    fixed_brand = forms.ModelChoiceField(
        label='Фиксированный бренд (если в файле нет бренда)',
        queryset=Brand.objects.all().order_by('name'),
        required=False,
    )
    save_mapping = forms.BooleanField(
        label='Сохранить маппинг на этом складе',
        required=False,
        initial=True,
    )

    def clean(self):
        cleaned = super().clean()
        preset_key = cleaned.get('preset') or PRESET_CUSTOM

        if preset_key != PRESET_CUSTOM:
            preset_settings = get_preset_settings(preset_key)
            if not preset_settings:
                self.add_error('preset', 'Неизвестный шаблон прайса')
                return cleaned
            form_vals = settings_to_form_initial(preset_settings)
            cleaned['header_row'] = form_vals['header_row']
            cleaned['data_start_row'] = form_vals['data_start_row']
            cleaned['col_article'] = form_vals['col_article']
            cleaned['col_brand'] = form_vals['col_brand']
            cleaned['col_price'] = form_vals['col_price']
            cleaned['col_qty'] = form_vals['col_qty']
            cleaned['col_external_id'] = form_vals['col_external_id']
            # fixed_brand из формы оставляем — шаблон его не задаёт

        article = (cleaned.get('col_article') or '').strip()
        price = (cleaned.get('col_price') or '').strip()
        if not article:
            self.add_error('col_article', 'Укажите колонку артикула или выберите шаблон')
        if not price:
            self.add_error('col_price', 'Укажите колонку цены или выберите шаблон')

        cleaned['col_article'] = article
        cleaned['col_price'] = price
        for key in ('col_brand', 'col_qty', 'col_external_id'):
            cleaned[key] = (cleaned.get(key) or '').strip()
        return cleaned

    def build_column_map(self) -> dict:
        mapping = {
            'article': self.cleaned_data.get('col_article', '').strip(),
            'price': self.cleaned_data.get('col_price', '').strip(),
        }
        for key, field in (
            ('brand', 'col_brand'),
            ('qty', 'col_qty'),
            ('external_id', 'col_external_id'),
        ):
            value = self.cleaned_data.get(field, '').strip()
            if value:
                mapping[key] = value
        return mapping

    def build_import_settings(self) -> dict:
        preset_key = self.cleaned_data.get('preset') or PRESET_CUSTOM
        fixed = self.cleaned_data.get('fixed_brand')
        fixed_id = fixed.pk if fixed else None

        if preset_key != PRESET_CUSTOM:
            settings = get_preset_settings(preset_key)
            if settings:
                settings['fixed_brand_id'] = fixed_id
                return settings

        return {
            'header_row': self.cleaned_data['header_row'],
            'data_start_row': self.cleaned_data['data_start_row'],
            'columns': self.build_column_map(),
            'fixed_brand_id': fixed_id,
            'preset': PRESET_CUSTOM,
        }
