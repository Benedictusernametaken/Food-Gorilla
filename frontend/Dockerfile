# Use an official, stable Node runtime as the base image
FROM node:22-slim

# Set the working directory inside the container
WORKDIR /app

# Copy package management files to install dependencies
COPY package*.json /app/

# Install frontend dependencies
RUN npm install

# Copy the rest of your frontend user interface source code
COPY . /app/

# Expose the port your development web server runs on
EXPOSE 3000

# Start the frontend application
CMD ["npm", "start"]