from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import DetailView, TemplateView
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.db import transaction
from django.utils import timezone
from shop.models import Product
from .inquiry_consent import CONSENT_REQUIRED_MESSAGE, is_personal_data_consent_given
from .models import Page, PriceInquiry, UsefulCategory, UsefulPost
from .seo import (
    seo_about,
    seo_contacts,
    seo_cms_page,
    seo_home,
    seo_useful_category,
    seo_useful_post,
    seo_useful_section_fallback,
)
from .tasks import enqueue_inquiry_notifications

DEFAULT_USEFUL_POSTS_PER_PAGE = 12

RESERVED_USEFUL_SHORT_SLUGS = frozenset(
    {
        "about",
        "contacts",
        "shop",
        "page",
        "useful",
        "admin",
        "ckeditor",
        "call-request",
        "price-inquiry",
        "suppliers",
        "images",
        "media",
        "static",
        "sitemap.xml",
        "robots.txt",
        "rss.xml",
    }
)


class HomeView(TemplateView):
    template_name = 'index.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Popular products (with is_featured flag)
        context['featured_products'] = Product.objects.filter(
            is_featured=True,
            in_stock=True,
        ).prefetch_related('images')[:15]

        context['new_products'] = Product.objects.filter(
            is_new=True,
            in_stock=True,
        ).prefetch_related('images')[:15]
        
        context['seo'] = seo_home(self.request)
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
            about_page = None
            context['page_content'] = None
            context['page_title'] = 'О компании'
        context['seo'] = seo_about(self.request, about_page)
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
            contacts_page = None
            context['page_content'] = None
            context['page_title'] = 'Контакты'
        context['seo'] = seo_contacts(self.request, contacts_page)
        return context


def paginate_queryset(request, queryset, per_page):
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get("page", 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages or 1)
    return page_obj


class UsefulSectionView(TemplateView):
    template_name = "useful_section.html"
    section_title = ""
    section_subtitle = ""
    section_slug = ""
    section_items = []

    def get_section_slug(self):
        return self.section_slug or self.kwargs.get("slug", "")

    def get_posts_queryset(self, category):
        if not category:
            return UsefulPost.objects.none()
        return category.posts.filter(is_active=True).order_by("-published_at", "order", "title")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = None
        section_slug = self.get_section_slug()
        if section_slug:
            category = UsefulCategory.objects.filter(slug=section_slug, is_active=True).first()

        posts_qs = self.get_posts_queryset(category)
        context["section_title"] = category.title if category else self.section_title
        context["section_subtitle"] = (
            category.description if category and category.description else self.section_subtitle
        )
        context["section_category"] = category
        context["section_items"] = self.section_items

        if category and posts_qs.exists():
            per_page = category.posts_per_page or DEFAULT_USEFUL_POSTS_PER_PAGE
            page_obj = paginate_queryset(self.request, posts_qs, per_page)
            context["section_posts"] = page_obj.object_list
            context["page_obj"] = page_obj
            context["paginator"] = page_obj.paginator
            context["is_paginated"] = page_obj.has_other_pages()
        else:
            context["section_posts"] = posts_qs
            context["page_obj"] = None
            context["paginator"] = None
            context["is_paginated"] = False

        if category:
            context["seo"] = seo_useful_category(
                self.request,
                category,
                fallback_subtitle=self.section_subtitle,
            )
        elif self.section_title:
            context["seo"] = seo_useful_section_fallback(
                self.request,
                self.section_title,
                self.section_subtitle,
            )

        return context


class NewsView(UsefulSectionView):
    section_slug = "news"
    section_title = "Новости"
    section_subtitle = "Обновления ассортимента, графика работы и сервисные объявления."
    section_items = [
        {
            "title": "Обновление ассортимента",
            "text": "Еженедельное поступление запчастей по основным маркам европейских грузовиков.",
            "meta": "Май 2026",
        },
        {
            "title": "График работы на праздники",
            "text": "Публикуем актуальный режим работы магазина и отгрузок в праздничные дни.",
            "meta": "Апрель 2026",
        },
        {
            "title": "Новые каналы связи",
            "text": "Добавлены дополнительные контакты для быстрой связи с менеджерами.",
            "meta": "Март 2026",
        },
    ]


class CatalogsView(UsefulSectionView):
    section_slug = "catalogs"
    section_title = "Каталоги"
    section_subtitle = "Подборки и справочные материалы для быстрого поиска нужных позиций."
    section_items = [
        {
            "title": "Каталог тормозной системы",
            "text": "Позиции по колодкам, дискам, барабанам и комплектам обслуживания.",
            "meta": "PDF / онлайн-версия",
        },
        {
            "title": "Каталог подвески и ходовой",
            "text": "Амортизаторы, рессоры, втулки и крепеж для популярных моделей.",
            "meta": "PDF / онлайн-версия",
        },
        {
            "title": "Каталог фильтров и расходников",
            "text": "Фильтры, ремни, технические жидкости и сопутствующие комплектующие.",
            "meta": "PDF / онлайн-версия",
        },
    ]


class ArticlesView(UsefulSectionView):
    section_slug = "articles"
    section_title = "Статьи"
    section_subtitle = "Полезные материалы по подбору и эксплуатации запчастей."
    section_items = [
        {
            "title": "Как подобрать аналог детали правильно",
            "text": "Ключевые шаги проверки OEM-номера и совместимости перед покупкой.",
            "meta": "Руководство",
        },
        {
            "title": "Частые ошибки при выборе фильтров",
            "text": "Разбираем типовые ошибки и даем чек-лист для быстрого контроля.",
            "meta": "Практика",
        },
        {
            "title": "Когда менять элементы тормозной системы",
            "text": "Базовые интервалы и признаки износа для безопасной эксплуатации.",
            "meta": "Обслуживание",
        },
    ]


class UsefulCategoryView(UsefulSectionView):
    section_title = "Полезное"
    section_subtitle = "Полезные материалы."


class UsefulPostDetailView(DetailView):
    model = UsefulPost
    template_name = "useful_post_detail.html"
    context_object_name = "post"
    pk_url_kwarg = "post_id"

    def get_queryset(self):
        return UsefulPost.objects.filter(is_active=True, category__is_active=True).select_related("category")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["seo"] = seo_useful_post(self.request, self.object)
        return context


def useful_category_legacy_redirect(request, slug):
    """Старый путь /useful/slug/ → канонический /slug/."""
    get_object_or_404(UsefulCategory, slug=slug, is_active=True)
    target = reverse("pages:useful_category", kwargs={"slug": slug})
    if request.GET:
        target = f"{target}?{request.GET.urlencode()}"
    return redirect(target, permanent=True)


def useful_category_by_slug(request, slug):
    if slug in RESERVED_USEFUL_SHORT_SLUGS:
        raise Http404
    get_object_or_404(UsefulCategory, slug=slug, is_active=True)
    return UsefulCategoryView.as_view()(request, slug=slug)


class PageDetailView(DetailView):
    model = Page
    template_name = 'page_detail.html'
    context_object_name = 'page'
    slug_url_kwarg = 'slug'
    
    def get_queryset(self):
        return Page.objects.filter(is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["seo"] = seo_cms_page(self.request, self.object)
        return context


@method_decorator(csrf_exempt, name='dispatch')
class CallRequestView(View):
    def post(self, request):
        try:
            print("=== CallRequestView DEBUG ===")
            print(f"POST data: {request.POST}")
            
            name = request.POST.get('userName')
            phone = request.POST.get('userPhone')
            email = request.POST.get('userEmail', '')
            comment = request.POST.get('comment', '')
            
            print(f"Parsed data: name={name}, phone={phone}, email={email}")
            
            if not name or not phone:
                print("ERROR: Missing required fields")
                return JsonResponse({
                    'success': False,
                    'message': 'Пожалуйста, заполните обязательные поля (Имя и Телефон)'
                })

            if not is_personal_data_consent_given(request.POST):
                return JsonResponse({
                    'success': False,
                    'message': CONSENT_REQUIRED_MESSAGE,
                })
            
            # Создаем новую заявку на звонок в PriceInquiry
            call_request = PriceInquiry.objects.create(
                name=name,
                phone=phone,
                email=email,
                comment=comment,
                request_type='call',
                personal_data_consent=True,
                consent_at=timezone.now(),
            )
            def _enqueue():
                try:
                    enqueue_inquiry_notifications(call_request.id)
                except Exception as enqueue_exc:
                    # Не ломаем ответ пользователю из-за недоступности очереди.
                    print(f"WARNING: enqueue notify task failed for inquiry {call_request.id}: {enqueue_exc}")
            transaction.on_commit(_enqueue)
            
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
            comment = request.POST.get('comment', '')
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

            if not is_personal_data_consent_given(request.POST):
                return JsonResponse({
                    'success': False,
                    'message': CONSENT_REQUIRED_MESSAGE,
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
                comment=comment,
                request_type='price',
                product_id=product_id,
                product_name=product_name,
                product_code=product_code or '',
                personal_data_consent=True,
                consent_at=timezone.now(),
            )
            def _enqueue():
                try:
                    enqueue_inquiry_notifications(price_inquiry.id)
                except Exception as enqueue_exc:
                    # Не ломаем ответ пользователю из-за недоступности очереди.
                    print(f"WARNING: enqueue notify task failed for inquiry {price_inquiry.id}: {enqueue_exc}")
            transaction.on_commit(_enqueue)
            
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


def server_error(request, *args, **kwargs):
    """Пользовательская страница 500 (DEBUG=False)."""
    return render(request, '500.html', status=500)
