import modal
from main import app as fastapi_app_instance

# Initialize Modal App
app = modal.App("vidgenai-app")  # This must be named 'app' for modal serve to pick it up by default

# Define container image
image = modal.Image.debian_slim().pip_install_from_requirements("requirements.txt")

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("vidgenai-env")]
)
@modal.concurrent(max_inputs=50)
@modal.asgi_app()
def fastapi_app():
    return fastapi_app_instance
