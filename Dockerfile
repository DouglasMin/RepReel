FROM public.ecr.aws/lambda/python:3.12

# Install dependencies into Lambda task root
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# Copy application source code
COPY src/ ${LAMBDA_TASK_ROOT}/src/

# Default CMD (overridden per function in serverless.yml)
CMD [ "src.handlers.ingest.handler" ]
