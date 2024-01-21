.PHONY: build up down

build:
	docker build -t nextolab/octopus .

up:
	docker run --rm -d \
	  --name octopus \
	  -v ~/.ssh/id_rsa.pub:/app/key.pub \
	  -v /var/run/docker.sock:/var/run/docker.sock \
	  -p 22:22 \
	  -p 80:80 \
	  nextolab/octopus

down:
	docker stop octopus
