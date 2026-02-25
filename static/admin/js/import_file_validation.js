/**
 * JavaScript для валидации DBF файлов в админке Django
 * 
 * Добавляет кнопку "Проверить файл" на страницу редактирования ImportFile
 * и выполняет AJAX запрос для валидации структуры файла
 */

(function($) {
    'use strict';
    
    $(document).ready(function() {
        console.log('🔍 ImportFile validation script loaded');
        console.log('file_type field:', $('#id_file_type').length);
        console.log('file field:', $('.field-file').length);
        
        // Проверяем что мы на странице редактирования ImportFile
        if ($('#id_file_type').length) {
            console.log('✅ Initializing validation');
            initValidation();
        } else {
            console.log('❌ file_type field not found');
        }
    });
    
    function initValidation() {
        // Создаем кнопку валидации
        const validateBtn = $('<button>')
            .attr({
                'type': 'button',
                'id': 'validate-file-btn',
                'class': 'button'
            })
            .css({
                'margin-left': '10px',
                'background-color': '#417690',
                'color': 'white'
            })
            .text('🔍 Проверить файл');
        
        // Создаем контейнер для результатов
        const resultsContainer = $('<div>')
            .attr('id', 'validation-results')
            .css({
                'margin-top': '15px',
                'padding': '15px',
                'border-radius': '4px',
                'display': 'none'
            });
        
        // Добавляем кнопку после поля file_type
        $('#id_file_type').parent().append(validateBtn);
        $('.field-file_type').after(resultsContainer);
        
        // Обработчик клика на кнопку
        validateBtn.on('click', function() {
            validateFile(validateBtn, resultsContainer);
        });
        
        // Автоматическая проверка при изменении типа файла
        $('#id_file_type').on('change', function() {
            // Сбрасываем результаты
            resultsContainer.slideUp().html('');
        });
    }
    
    function validateFile(btn, resultsContainer) {
        const fileType = $('#id_file_type').val();
        const fileId = getFileIdFromUrl();
        
        // Проверки
        if (!fileId) {
            showError(resultsContainer, '❌ Сначала сохраните файл');
            return;
        }
        
        if (!fileType) {
            showError(resultsContainer, '❌ Сначала выберите тип файла');
            return;
        }
        
        // Блокируем кнопку и показываем процесс
        btn.prop('disabled', true).text('⏳ Проверка...');
        resultsContainer.slideUp();
        
        // AJAX запрос
        $.ajax({
            url: `/admin/shop/importfile/${fileId}/validate/`,
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            success: function(response) {
                if (response.success) {
                    showValidationResults(resultsContainer, response);
                } else {
                    showError(resultsContainer, response.message || 'Ошибка валидации');
                }
            },
            error: function(xhr, status, error) {
                showError(resultsContainer, `❌ Ошибка сервера: ${error}`);
            },
            complete: function() {
                btn.prop('disabled', false).text('🔍 Проверить файл');
            }
        });
    }
    
    function showValidationResults(container, data) {
        let html = '';
        let bgColor = '';
        
        if (data.is_valid) {
            // Успешная валидация
            bgColor = '#d4edda';
            html += '<h3 style="color: #155724; margin-top: 0;">✅ Файл прошел валидацию!</h3>';
            html += `<p><strong>Тип:</strong> ${$('#id_file_type option:selected').text()}</p>`;
            html += `<p><strong>Записей:</strong> ${data.record_count.toLocaleString()}</p>`;
            html += `<p><strong>Найдено полей:</strong> ${data.found_fields.length}</p>`;
            
            if (data.warnings && data.warnings.length > 0) {
                html += '<div style="margin-top: 10px; padding: 10px; background: #fff3cd; border-left: 4px solid #ffc107;">';
                html += '<strong>⚠️ Предупреждения:</strong><ul>';
                data.warnings.forEach(function(warning) {
                    html += `<li>${warning}</li>`;
                });
                html += '</ul></div>';
            }
            
            html += '<p style="margin-top: 15px; color: #155724;"><strong>✓ Можно запускать импорт!</strong></p>';
            
        } else {
            // Ошибка валидации
            bgColor = '#f8d7da';
            html += '<h3 style="color: #721c24; margin-top: 0;">❌ Файл не прошел валидацию</h3>';
            html += `<div style="white-space: pre-wrap; font-family: monospace; background: white; padding: 10px; border-radius: 4px;">${data.message}</div>`;
            
            if (data.suggested_type) {
                html += `<p style="margin-top: 15px; padding: 10px; background: #cce5ff; border-left: 4px solid #004085;">`;
                html += `<strong>💡 Подсказка:</strong> Попробуйте изменить тип на "<strong>${getFileTypeLabel(data.suggested_type)}</strong>"`;
                html += `</p>`;
            }
        }
        
        container.html(html)
                 .css({'background-color': bgColor, 'border': '1px solid ' + (data.is_valid ? '#c3e6cb' : '#f5c6cb')})
                 .slideDown();
    }
    
    function showError(container, message) {
        const html = `<div style="color: #721c24; background-color: #f8d7da; padding: 15px; border-radius: 4px; border: 1px solid #f5c6cb;">${message}</div>`;
        container.html(html).slideDown();
    }
    
    function getFileIdFromUrl() {
        // Извлекаем ID из URL: /admin/shop/importfile/123/change/
        const match = window.location.pathname.match(/importfile\/(\d+)\//);
        return match ? match[1] : null;
    }
    
    function getFileTypeLabel(type) {
        const labels = {
            'brands': 'Бренды',
            'products': 'Товары',
            'analogs': 'OE Аналоги'
        };
        return labels[type] || type;
    }
    
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    
})(django.jQuery);

