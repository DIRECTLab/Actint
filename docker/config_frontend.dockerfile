FROM node:lts-alpine3.22

WORKDIR /app

COPY ./Groundtruth-Simulator/config-generator .

RUN npm install

CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"]