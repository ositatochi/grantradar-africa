from django import forms

from apps.tracker.models import Note, PipelineItem


class PipelineItemForm(forms.ModelForm):
    class Meta:
        model = PipelineItem
        fields = ["status", "submitted_at"]
        widgets = {
            "submitted_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Keep private notes about this application.",
                }
            )
        }
