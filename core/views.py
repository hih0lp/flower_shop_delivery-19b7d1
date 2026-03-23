import stripe
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.conf import settings
from django.utils import timezone
from .models import Product, Category, Order, OrderItem
from .cart import Cart
from .forms import CheckoutForm

stripe.api_key = settings.STRIPE_SECRET_KEY


def home(request):
    popular_products = Product.objects.filter(is_available=True)[:8]
    return render(request, 'core/home.html', {'popular_products': popular_products})


def catalog(request):
    category_id = request.GET.get('category')
    products = Product.objects.filter(is_available=True)
    
    if category_id:
        products = products.filter(category_id=category_id)
    
    categories = Category.objects.all()
    
    if request.htmx:
        return render(request, 'core/partials/product_list.html', {'products': products})
    
    return render(request, 'core/catalog.html', {
        'products': products,
        'categories': categories,
    })


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk, is_available=True)
    return render(request, 'core/product_detail.html', {'product': product})


@require_POST
def cart_add(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id, is_available=True)
    quantity = int(request.POST.get('quantity', 1))
    cart.add(product, quantity)
    
    if request.htmx:
        return render(request, 'core/partials/cart_count.html', {'cart_count': len(cart)})
    
    return redirect('cart_detail')


def cart_detail(request):
    cart = Cart(request)
    return render(request, 'core/cart_detail.html', {'cart': cart})


@require_POST
def cart_remove(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    cart.remove(product)
    
    if request.htmx:
        return render(request, 'core/partials/cart_detail.html', {'cart': cart})
    
    return redirect('cart_detail')


@require_POST
def cart_update(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    quantity = int(request.POST.get('quantity', 1))
    
    if quantity > 0:
        cart.add(product, quantity, override_quantity=True)
    else:
        cart.remove(product)
    
    if request.htmx:
        return render(request, 'core/partials/cart_detail.html', {'cart': cart})
    
    return redirect('cart_detail')


def checkout(request):
    cart = Cart(request)
    
    if len(cart) == 0:
        messages.warning(request, 'Ваша корзина пуста')
        return redirect('catalog')
    
    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.total_price = cart.get_total_price()
            
            if request.user.is_authenticated:
                order.user = request.user
            
            order.save()
            
            for item in cart:
                OrderItem.objects.create(
                    order=order,
                    product=item['product'],
                    quantity=item['quantity']
                )
            
            request.session['order_id'] = order.id
            return redirect('create_payment_intent')
    else:
        initial_data = {}
        if request.user.is_authenticated and hasattr(request.user, 'profile'):
            initial_data['delivery_address'] = request.user.profile.preferred_delivery_address
        form = CheckoutForm(initial=initial_data)
    
    return render(request, 'core/checkout.html', {
        'cart': cart,
        'form': form,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
    })


@login_required
def create_payment_intent(request):
    order_id = request.session.get('order_id')
    if not order_id:
        return HttpResponseBadRequest('Order not found')
    
    order = get_object_or_404(Order, id=order_id)
    
    try:
        intent = stripe.PaymentIntent.create(
            amount=int(order.total_price * 100),
            currency='rub',
            metadata={'order_id': order.id},
        )
        
        order.stripe_payment_intent_id = intent.id
        order.save()
        
        return JsonResponse({'clientSecret': intent.client_secret})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


def checkout_success(request):
    order_id = request.session.get('order_id')
    if order_id:
        order = get_object_or_404(Order, id=order_id)
        order.status = 'paid'
        order.save()
        
        cart = Cart(request)
        cart.clear()
        
        if 'order_id' in request.session:
            del request.session['order_id']
    
    return render(request, 'core/checkout_success.html')


def checkout_cancel(request):
    return render(request, 'core/checkout_cancel.html')


@login_required
def order_list(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'core/order_list.html', {'orders': orders})


@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    return render(request, 'core/order_detail.html', {'order': order})