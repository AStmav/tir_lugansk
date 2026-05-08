from django.urls import path
from . import views

app_name = 'pages'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('about/', views.AboutView.as_view(), name='about'),
    path('contacts/', views.ContactsView.as_view(), name='contacts'),
    path('useful/post/<int:post_id>/', views.UsefulPostDetailView.as_view(), name='useful_post_detail'),
    path('useful/<slug:slug>/', views.UsefulCategoryView.as_view(), name='useful_category'),
    path('news/', views.legacy_useful_redirect, {"slug": "news"}, name='news'),
    path('catalogs/', views.legacy_useful_redirect, {"slug": "catalogs"}, name='catalogs'),
    path('articles/', views.legacy_useful_redirect, {"slug": "articles"}, name='articles'),
    path('page/<slug:slug>/', views.PageDetailView.as_view(), name='page_detail'),
    path('call-request/', views.CallRequestView.as_view(), name='call_request'),
    path('price-inquiry/', views.PriceInquiryView.as_view(), name='price_inquiry'),
] 