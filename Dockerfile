# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /shared

# Copy the current directory contents into the container at /shared
COPY shared/ /shared

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Make port 80 available to the world outside this container
EXPOSE 80

# Define environment variable
ENV NAME=World

# Run shared.py when the container launches
CMD ["python", "hello_team.py"]
