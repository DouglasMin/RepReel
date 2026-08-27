FROM public.ecr.aws/lambda/python:3.12

# Install static ffmpeg & ffprobe
RUN dnf install -y tar xz && \
    curl -sL https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz | tar -xJ --strip-components=1 -C /usr/local/bin/ ffmpeg-7.1-amd64-static/ffmpeg ffmpeg-7.1-amd64-static/ffprobe 2>/dev/null || \
    (curl -sL https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz | tar -xJ -C /tmp && cp /tmp/ffmpeg-*-amd64-static/ffmpeg /tmp/ffmpeg-*-amd64-static/ffprobe /usr/local/bin/ && rm -rf /tmp/ffmpeg-*) && \
    chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe && \
    dnf clean all

# Install dependencies into Lambda task root
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# Copy application source code
COPY src/ ${LAMBDA_TASK_ROOT}/src/

# Default CMD (overridden per function in serverless.yml)
CMD [ "src.handlers.ingest.handler" ]
