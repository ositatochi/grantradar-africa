from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.accounts.forms import UserProfileForm


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated.")
            return redirect("accounts:profile")
    else:
        form = UserProfileForm(instance=request.user)
    return render(request, "accounts/profile.html", {"form": form})
