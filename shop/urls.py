from django.urls import path
from . import views

app_name = 'shop'

urlpatterns = [
    path('catalog/', views.CatalogView.as_view(), name='catalog'),
    path('search-autocomplete/', views.search_autocomplete, name='search_autocomplete'),
    path('product/<slug:slug>/', views.ProductView.as_view(), name='product'),
] 