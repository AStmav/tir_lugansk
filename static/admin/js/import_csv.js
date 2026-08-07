document.addEventListener('DOMContentLoaded', function() {
    // Добавляем кнопку "Загрузить CSV" в changelist
    const changelist = document.querySelector('.changelist-search');
    if (changelist) {
        const uploadButton = document.createElement('a');
        uploadButton.href = 'upload/';
        uploadButton.className = 'addlink';
        uploadButton.innerHTML = '📁 Загрузить CSV файл';
        uploadButton.style.marginLeft = '10px';
        changelist.appendChild(uploadButton);
    }
    
    // Обработчики для кнопок импорта и отмены
    document.addEventListener('click', function(e) {
        // Кнопка запуска импорта
        if (e.target.classList.contains('btn-import-csv')) {
            e.preventDefault();
            
            const fileId = e.target.getAttribute('data-id');
            const button = e.target;
            
            if (confirm('Запустить импорт данных из этого файла? Файл уже загружен на сервер и готов к обработке.')) {
                button.disabled = true;
                button.innerHTML = '⏳ Запускаю...';
                button.style.background = '#999';
                
                fetch(`process/${fileId}/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Показываем сообщение об успехе
                        showMessage('success', data.message);
                        
                        // Перенаправляем на страницу прогресса или обновляем страницу
                        if (data.redirect_url) {
                            setTimeout(() => {
                                window.location.href = data.redirect_url;
                            }, 1000);
                        } else {
                            setTimeout(() => {
                                window.location.reload();
                            }, 2000);
                        }
                    } else {
                        showMessage('error', 'Ошибка: ' + data.message);
                        button.disabled = false;
                        button.innerHTML = '▶ Запустить импорт';
                        button.style.background = '#417690';
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    showMessage('error', 'Произошла ошибка при запуске импорта');
                    button.disabled = false;
                    button.innerHTML = '▶ Запустить импорт';
                    button.style.background = '#417690';
                });
            }
        }
        
        // Кнопка отмены импорта
        if (e.target.classList.contains('btn-cancel-import')) {
            e.preventDefault();
            
            const fileId = e.target.getAttribute('data-id');
            const button = e.target;
            
            if (confirm('Отменить импорт? Процесс будет остановлен.')) {
                button.disabled = true;
                button.innerHTML = '⏳ Отменяю...';
                button.style.background = '#999';
                
                fetch(`cancel/${fileId}/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        showMessage('success', data.message);
                        setTimeout(() => {
                            window.location.reload();
                        }, 1500);
                    } else {
                        showMessage('error', 'Ошибка: ' + data.message);
                        button.disabled = false;
                        button.innerHTML = '⏹ Отменить';
                        button.style.background = '#dc3545';
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    showMessage('error', 'Произошла ошибка при отмене импорта');
                    button.disabled = false;
                    button.innerHTML = '⏹ Отменить';
                    button.style.background = '#dc3545';
                });
            }
        }
    });
    
    // Функция для показа сообщений
    function showMessage(type, message) {
        // Удаляем предыдущие сообщения
        const existingMessages = document.querySelectorAll('.import-message');
        existingMessages.forEach(msg => msg.remove());
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `import-message alert-${type}`;
        messageDiv.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            padding: 15px 20px;
            border-radius: 5px;
            font-weight: bold;
            min-width: 300px;
            max-width: 500px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            ${type === 'success' ? 
                'background: #d4edda; border: 2px solid #c3e6cb; color: #155724;' : 
                'background: #f8d7da; border: 2px solid #f5c6cb; color: #721c24;'
            }
        `;
        messageDiv.innerHTML = `
            <span style="margin-right: 10px;">${type === 'success' ? '✅' : '❌'}</span>
            ${message}
            <button onclick="this.parentElement.remove()" style="
                float: right; 
                background: none; 
                border: none; 
                font-size: 18px; 
                cursor: pointer;
                margin-left: 10px;
            ">×</button>
        `;
        
        document.body.appendChild(messageDiv);
        
        // Автоматически убираем сообщение через 5 секунд
        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.remove();
            }
        }, 5000);
    }
    
    // Прогресс-бар для загрузки файла
    const fileInput = document.getElementById('id_csv_file');
    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                // Проверяем размер файла (максимум 100MB)
                if (file.size > 100 * 1024 * 1024) {
                    showMessage('error', 'Файл слишком большой. Максимальный размер: 100MB');
                    e.target.value = '';
                    return;
                }
                
                // Проверяем расширение
                if (!file.name.toLowerCase().endsWith('.csv')) {
                    showMessage('error', 'Пожалуйста, выберите файл с расширением .csv');
                    e.target.value = '';
                    return;
                }
                
                // Показываем информацию о файле
                const info = document.createElement('div');
                info.className = 'file-info';
                info.style.cssText = `
                    margin-top: 10px;
                    padding: 10px;
                    background: #e7f3ff;
                    border: 1px solid #b8daff;
                    border-radius: 4px;
                    color: #0056b3;
                `;
                info.innerHTML = `
                    <strong>✅ Файл готов к загрузке:</strong><br>
                    📄 Название: ${file.name}<br>
                    📊 Размер: ${(file.size / 1024 / 1024).toFixed(2)} MB<br>
                    🔧 Тип: ${file.type || 'text/csv'}
                `;
                
                // Удаляем предыдущую информацию если есть
                const existingInfo = fileInput.parentNode.querySelector('.file-info');
                if (existingInfo) {
                    existingInfo.remove();
                }
                
                fileInput.parentNode.appendChild(info);
                showMessage('success', 'Файл выбран успешно! Теперь нажмите "Загрузить файл"');
            }
        });
    }
    
    // Автообновление страницы списка импортов каждые 30 секунд если есть активные импорты
    const activeImports = document.querySelectorAll('.btn-cancel-import');
    if (activeImports.length > 0) {
        console.log('Обнаружены активные импорты, включено автообновление');
        setTimeout(() => {
            window.location.reload();
        }, 30000);
    }
}); 