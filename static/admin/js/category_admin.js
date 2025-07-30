document.addEventListener('DOMContentLoaded', function() {
    console.log('Category admin JS loaded');
    
    // Создаем модальное окно
    const modalHTML = `
        <div id="categoryModal" class="category-modal">
            <div class="category-modal-content">
                <div class="category-modal-header">
                    <h3>Редактировать категорию</h3>
                    <button type="button" class="category-modal-close">&times;</button>
                </div>
                <div class="category-modal-body">
                    <form id="categoryForm">
                        <input type="hidden" id="categoryId">
                        <div class="form-group">
                            <label for="categoryName">Название:</label>
                            <input type="text" id="categoryName" required>
                        </div>
                        <div class="form-group">
                            <label for="categoryParent">Родительская категория:</label>
                            <select id="categoryParent">
                                <option value="">-- Основная категория --</option>
                            </select>
                        </div>
                    </form>
                </div>
                <div class="category-modal-footer">
                    <button type="button" class="btn-cancel">Отмена</button>
                    <button type="button" class="btn-save">Сохранить</button>
                </div>
            </div>
        </div>
    `;
    
    // Добавляем модальное окно в DOM
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    
    const modal = document.getElementById('categoryModal');
    const form = document.getElementById('categoryForm');
    const categoryIdInput = document.getElementById('categoryId');
    const categoryNameInput = document.getElementById('categoryName');
    const categoryParentSelect = document.getElementById('categoryParent');
    
    // Загружаем список категорий для выбора родительской
    function loadParentCategories() {
        fetch('/admin/shop/category/', {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.text())
        .then(html => {
            // Парсим HTML и извлекаем категории
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const rows = doc.querySelectorAll('table.results tbody tr');
            
            // Очищаем select
            categoryParentSelect.innerHTML = '<option value="">-- Основная категория --</option>';
            
            rows.forEach(row => {
                const nameCell = row.querySelector('.field-tree_name');
                const editBtn = row.querySelector('.btn-edit-category');
                
                if (nameCell && editBtn) {
                    const categoryId = editBtn.getAttribute('data-id');
                    const categoryName = editBtn.getAttribute('data-name');
                    const level = (nameCell.textContent.match(/—/g) || []).length / 2;
                    
                    // Добавляем только основные категории (level = 0) как возможных родителей
                    if (level === 0) {
                        const option = document.createElement('option');
                        option.value = categoryId;
                        option.textContent = categoryName;
                        categoryParentSelect.appendChild(option);
                    }
                }
            });
        })
        .catch(error => {
            console.error('Ошибка загрузки категорий:', error);
        });
    }
    
    // Обработчики для кнопок редактирования
    function attachEditButtons() {
        document.querySelectorAll('.btn-edit-category').forEach(button => {
            button.removeEventListener('click', handleEditClick); // Удаляем старые обработчики
            button.addEventListener('click', handleEditClick);
        });
    }
    
    function handleEditClick(e) {
        e.preventDefault();
        e.stopPropagation();
        
        const button = e.target;
        const categoryId = button.getAttribute('data-id');
        const categoryName = button.getAttribute('data-name');
        const parentId = button.getAttribute('data-parent');
        
        console.log('Edit category:', { categoryId, categoryName, parentId });
        
        // Заполняем форму
        categoryIdInput.value = categoryId;
        categoryNameInput.value = categoryName;
        categoryParentSelect.value = parentId || '';
        
        // Загружаем категории и показываем модальное окно
        loadParentCategories();
        modal.style.display = 'block';
    }
    
    // Закрытие модального окна
    function closeModal() {
        modal.style.display = 'none';
        form.reset();
    }
    
    // Обработчики закрытия
    modal.querySelector('.category-modal-close').addEventListener('click', closeModal);
    modal.querySelector('.btn-cancel').addEventListener('click', closeModal);
    
    // Закрытие по клику вне модального окна
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            closeModal();
        }
    });
    
    // Сохранение изменений
    modal.querySelector('.btn-save').addEventListener('click', function() {
        const categoryId = categoryIdInput.value;
        const categoryName = categoryNameInput.value.trim();
        const parentId = categoryParentSelect.value;
        
        if (!categoryName) {
            alert('Пожалуйста, введите название категории');
            return;
        }
        
        console.log('Saving category:', { categoryId, categoryName, parentId });
        
        const formData = new FormData();
        formData.append('id', categoryId);
        formData.append('name', categoryName);
        formData.append('parent', parentId);
        
        fetch('/admin/shop/category/update_category/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Категория успешно обновлена!');
                closeModal();
                // Перезагружаем страницу для обновления списка
                window.location.reload();
            } else {
                alert('Ошибка: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Ошибка:', error);
            alert('Произошла ошибка при сохранении');
        });
    });
    
    // Инициализация
    attachEditButtons();
    
    // Переинициализация после обновления содержимого страницы (для Django admin)
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.type === 'childList') {
                attachEditButtons();
            }
        });
    });
    
    const targetNode = document.querySelector('#result_list');
    if (targetNode) {
        observer.observe(targetNode, { childList: true, subtree: true });
    }
}); 