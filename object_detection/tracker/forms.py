import os

from django import forms


ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


class ImageUploadForm(forms.Form):
    image = forms.FileField(label="Select Image")

    def clean_image(self):
        image = self.cleaned_data["image"]
        extension = os.path.splitext(image.name)[1].lower()

        if extension not in ALLOWED_IMAGE_EXTENSIONS:
            raise forms.ValidationError(
                "Unsupported image format. Use JPG, PNG, WEBP, or BMP."
            )

        return image


class VideoUploadForm(forms.Form):
    video = forms.FileField(
        label="Select Video"
    )

    start_time = forms.CharField(
        required=False,
        label="Start Time (HH:MM:SS)"
    )

    end_time = forms.CharField(
        required=False,
        label="End Time (HH:MM:SS)"
    )

    track_id = forms.IntegerField(
        required=False,
        label="Track ID"
    )