import modal

image = modal.Image.from_dockerfile("Dockerfile")

app = modal.App("vidgenai-backend-docker", image=image)

# Modal will inject them as environment variables.
secrets = [modal.Secret.from_name("vidgenai-secrets")]


# Keep one warm container to cut cold-starts; scale down after 5 minutes of idle.
@app.function(
    region="ap-south-1",
    cpu=1.0,
    memory=1024,
    secrets=secrets,
    scaledown_window=200
)
@modal.asgi_app()              # use this for full FastAPI apps with many routes
def fastapi_app():
    # All imports here run inside the container
    from main import app as application
    return application
