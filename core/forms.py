from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Order


class CustomUserCreationForm(UserCreationForm):
    phone_number = forms.CharField(max_length=20, required=False, label='Номер телефона')
    
    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('phone_number',)


class CheckoutForm(forms.ModelForm):
    delivery_time = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        label='Время доставки'
    )
    
    class Meta:
        model = Order
        fields = ['delivery_address', 'delivery_time']
        widgets = {
            'delivery_address': forms.Textarea(attrs={'rows': 3}),
        }
        labels = {
            'delivery_address': 'Адрес доставки',
        }