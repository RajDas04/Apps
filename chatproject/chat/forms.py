from django import forms
from .models import Message
from .models import Room

class MessageForm(forms.ModelForm):
    content = forms.CharField(widget=forms.Textarea
                              (attrs={'rows':2, 'placeholder': 'Message', 'class': 'form-control w-100'})
                              ,max_length=2000)
    
    class Meta:
        model = Message
        fields = ('content',)


class RoomForm(forms.ModelForm):
    
    class Meta:
        model = Room
        fields = ['name']
