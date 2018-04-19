from django.shortcuts import render
from .forms import LabForm

def lab(request):
    form = LabForm()
    
    return render(request,'lab.html',{'form':form})
