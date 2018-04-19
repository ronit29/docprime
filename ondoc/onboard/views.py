from django.shortcuts import render, redirect, HttpResponse
from .forms import LabForm, OTPForm
from ondoc.diagnostic.models import LabOnboardingToken, Lab
from random import randint


def lab(request):

    lab_id = request.GET.get('lab_id')
    token = request.GET.get('token')
    verified_token = request.GET.get('verified_token')

    if not lab_id or not token:
        return HttpResponse('error')

    existing = None

    try:
        existing = LabOnboardingToken.objects.filter(lab_id=lab_id,token=token).order_by('-created_at')[0]
    except:
        pass

    if not existing:
        return HttpResponse('error')

    if not existing.lab:
        return HttpResponse('error')


    if existing.status != LabOnboardingToken.GENERATED:
        return render(request,'access_denied.html')

    if not verified_token:
        form = OTPForm()
        return render(request,'otp.html',{'form':form})

    if existing.verified_token == verified_token:
        form = LabForm(instance = existing.lab)
        return render(request,'lab.html',{'form':form})


def otp(request):
    if request.method == 'POST':
        action = request.POST.get('_resend_otp')
        if action:
            otp = randint(1000000000, 9000000000)
            print(otp)
            request.session['otp'] = otp
            lab_id = request.GET.get('lab_id')
            # token = request.GET.get('lab_id')
            return redirect("/onboard/lab?lab_id="+lab_id, permanent=False)
        else:    
            stored_otp = str(request.session.get('otp',''))
            otp = request.POST.get('otp')
            if otp == stored_otp:
                return redirect("/onboard/lab?token=1438749146&lab_id=1", permanent=False)


    else:
        form = OTPForm()
        return render(request,'otp.html',{'form':form})


def generate(request):
    lab_id = request.GET.get('lab_id')
    lab = Lab.objects.get(pk=lab_id)

    LabOnboardingToken.objects.filter(lab_id=lab_id, status=LabOnboardingToken.GENERATED).update(status=LabOnboardingToken.REJECTED)
    
    token = LabOnboardingToken(status=1,lab_id=lab_id, token=randint(1000000000, 9000000000),verified_token=randint(1000000000, 9000000000) )
    token.save()
    url = 'ondoc.com/onboard/lab?token='+str(token.token)+'&lab_id='+str(lab_id)
    return HttpResponse('generated_url is '+url)
