from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView, DetailView
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from shop.models import Product
from .models import Contact, Page


class HomeView(TemplateView):
    template_name = 'index.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Popular products (with is_featured flag)
        context['featured_products'] = Product.objects.filter(
            is_featured=True, 
            in_stock=True
        )[:5]
        
        # New products (with is_new flag)
        context['new_products'] = Product.objects.filter(
            is_new=True, 
            in_stock=True
        )[:5]
        
        return context


class AboutView(TemplateView):
    template_name = 'about.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Пытаемся получить страницу "О компании" из БД
        try:
            about_page = Page.objects.get(page_type='about', is_active=True)
            context['page_content'] = about_page.content
            context['page_title'] = about_page.title
        except Page.DoesNotExist:
            context['page_content'] = None
            context['page_title'] = 'О компании'
        return context


class ContactsView(TemplateView):
    template_name = 'contacts.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Пытаемся получить страницу "Контакты" из БД
        try:
            contacts_page = Page.objects.get(page_type='contacts', is_active=True)
            context['page_content'] = contacts_page.content
            context['page_title'] = contacts_page.title
        except Page.DoesNotExist:
            context['page_content'] = None
            context['page_title'] = 'Контакты'
        return context


class PageDetailView(DetailView):
    model = Page
    template_name = 'page_detail.html'
    context_object_name = 'page'
    slug_url_kwarg = 'slug'
    
    def get_queryset(self):
        return Page.objects.filter(is_active=True)


@method_decorator(csrf_exempt, name='dispatch')
class CallRequestView(View):
    def post(self, request):
        try:
            name = request.POST.get('userName')
            phone = request.POST.get('userPhone')
            
            if not name or not phone:
                return JsonResponse({
                    'success': False,
                    'message': 'Пожалуйста, заполните все поля'
                })
            
            # Создаем новую заявку на звонок
            contact = Contact.objects.create(
                name=name,
                phone=phone
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Заявка успешно отправлена!'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': 'Произошла ошибка при отправке заявки'
            })
