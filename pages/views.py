from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView, DetailView
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from shop.models import Product
from .models import Page, PriceInquiry


class HomeView(TemplateView):
    template_name = 'index.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Popular products (with is_featured flag)
        context['featured_products'] = Product.objects.filter(
            is_featured=True, 
            in_stock=True
        )[:15]
        
        # New products (with is_new flag)
        context['new_products'] = Product.objects.filter(
            is_new=True, 
            in_stock=True
        )[:15]
        
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
            print("=== CallRequestView DEBUG ===")
            print(f"POST data: {request.POST}")
            
            name = request.POST.get('userName')
            phone = request.POST.get('userPhone')
            email = request.POST.get('userEmail', '')
            
            print(f"Parsed data: name={name}, phone={phone}, email={email}")
            
            if not name or not phone:
                print("ERROR: Missing required fields")
                return JsonResponse({
                    'success': False,
                    'message': 'Пожалуйста, заполните обязательные поля (Имя и Телефон)'
                })
            
            # Создаем новую заявку на звонок в PriceInquiry
            call_request = PriceInquiry.objects.create(
                name=name,
                phone=phone,
                email=email,
                request_type='call'
            )
            
            print(f"SUCCESS: Created call request with ID {call_request.id}")
            
            return JsonResponse({
                'success': True,
                'message': 'Заявка успешно отправлена!'
            })
            
        except Exception as e:
            print(f"ERROR in CallRequestView: {e}")
            return JsonResponse({
                'success': False,
                'message': 'Произошла ошибка при отправке заявки'
            })


@method_decorator(csrf_exempt, name='dispatch')
class PriceInquiryView(View):
    def post(self, request):
        try:
            print("=== PriceInquiryView DEBUG ===")
            print(f"POST data: {request.POST}")
            
            name = request.POST.get('userName')
            phone = request.POST.get('userPhone')
            email = request.POST.get('userEmail', '')
            product_id = request.POST.get('product_id')
            product_name = request.POST.get('product_name')
            product_code = request.POST.get('product_code')
            
            print(f"Parsed data: name={name}, phone={phone}, email={email}")
            print(f"Product data: id={product_id}, name={product_name}, code={product_code}")
            
            if not name or not phone:
                print("ERROR: Missing required fields")
                return JsonResponse({
                    'success': False,
                    'message': 'Пожалуйста, заполните обязательные поля (Имя и Телефон)'
                })
            
            if not product_id or not product_name:
                print("ERROR: Missing product info")
                return JsonResponse({
                    'success': False,
                    'message': 'Информация о товаре не найдена'
                })
            
            # Создаем новый запрос цены
            price_inquiry = PriceInquiry.objects.create(
                name=name,
                phone=phone,
                email=email,
                request_type='price',
                product_id=product_id,
                product_name=product_name,
                product_code=product_code or ''
            )
            
            print(f"SUCCESS: Created PriceInquiry with ID {price_inquiry.id}")
            
            return JsonResponse({
                'success': True,
                'message': 'Запрос успешно отправлен! Мы свяжемся с вами в ближайшее время.'
            })
            
        except Exception as e:
            print(f"ERROR in PriceInquiryView: {e}")
            return JsonResponse({
                'success': False,
                'message': 'Произошла ошибка при отправке запроса'
            })
