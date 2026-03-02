# My Flask Webpage
A python flask web app running on docker with uWSGI and nginx.

## Setup virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Note: On Windows the activate path is different:
```bash
.\.venv\Scripts\activate

# To deactivate
.\.venv\Scripts\deactivate
```

To upgrade pip:
```bash
python -m pip install --upgrade pip
```

PDM is used for package management. 
```bash
pdm install
```

Note: On windows uwsgi cannot be installed because it is a unix only package. You need to skip the installation process.


# Deployment

## Development Environment

Set the `FLASK_APP` environment variable.
```bash
export FLASK_APP=src/my_flask_webpage/__init__.py
```

On windows in windows powershell:
```bash
$env:FLASK_APP = "src/my_flask_webpage/__init__.py"
```

## PDM script
As shortcut a pdm script is set, which runs the flask app and sets the environment variable.
```bash
pdm run dev
```
It is great for fast html/css and database prototyping. As database a SQLite database is used for this
simple and fast development environment. For production a postgres database is used and the app is served
by a nginx reverse proxy. These services can also be run in development mode to test a close to production
environment version of the app locally. But it is slightly more complex to set up. After each change in the
web app the docker container needs to be rebuilt and restarted. So, you end up rebuilding the container 
(`docker build -t...`) and restarting the docker-compose services (`docker-compose up -d`) after each change.

## Production Environment

### Build the Docker Image
```bash
docker build -t my_flask_webpage .
```

Note: Obtain requirements from pdm package manager.
```bash
pdm export -f requirements --without-hashes > requirements.txt
```


A note to windows users: You need C++ build tools to build the image. You can download it from [here](https://visualstudio.microsoft.com/visual-cpp-build-tools/).
These are necessary for the `uwsgi` package. After installing the build tools, you need to run the following command:
```bash
"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
```

### Run the Docker Container
```bash
docker run -d -p 3031:3031 my_flask_webpage
```

For local testing change in `uwsgi.ini`, `socket` to `http`. Then it does not use a socket but a http connection for
communication. This is useful for local testing. In production, the socket should be used together with a web server like
nginx, which functions as a reverse proxy.

Connection Diagram:

Browser → Nginx (HTTPS, HTTP) → uWSGI (via socket) → flask web application

### Initialize the Database

On Windows:

```bash
docker exec -it <container_id> bash
python -m 'app.setup.init_db'
```

On Linux:

```bash
docker exec -it <container_id> bash
python -m app.setup.init_db
```

In productive environment:
```bash
docker exec -it <container_id> bash
ubuntu@023a4a99b06e:/home/app/src$ python -m setup.init_db
```

## Docker Compose Multi-Container Environment 

So far, we have built the image and run the container. Now we will use Docker Compose to implement additional services
like nginx (reverse-proxy), handling the outside traffic, and a postgres database, which is faster for many requests and 
read/write processes than SQLite.

Both containers are executed in read-only mode, which means the entire root filesystem of the container is mounted as 
read-only.
Consequences:
- Prevents the container from writing to any part of its filesystem (except for **tmpfs mounts and volumes**).
- It's a security hardening measure — helpful in production to reduce the risk of file tampering or malicious writes.

As small digression, I want to address the principal components of which a docker-compose file consists of:
- `version`: The version of the docker-compose version that is used for building the services.
- `services`: The services that are defined in the docker-compose file. Each service has its own configuration and consists
of an image, environment variables, volumes, and ports.
- `networks`: networks connect one service to another. They are used to communicate between services e. g. the web app 
needs to receive requests from the reverse proxy and the other way around. The reverse proxy needs to forward the requests 
to the web app.
- `volumes`: volumes are used to store data persistently that is shared between containers and the host system.
- `environment`: environment variables are used to set configuration values for the services.

### Excursus: Volumes
Why do we need volumes?
- Data persistence: Data is stored in volumes and is not lost when the container is stopped or removed.
- Isolation – Volumes isolate storage from container internals — safe and clean.
- Sharing – Volumes can be shared across multiple containers.
- Backup/Restore – Easier to back up or move to other systems.
- Performance – On Linux, volumes are often more performant than bind mounts.

Key characteristics:

| Feature                              | Description                                                                                         |
|--------------------------------------|-----------------------------------------------------------------------------------------------------|
| **Managed by Docker**                | Docker tracks volumes and stores them in its own directory (e.g. `/var/lib/docker/volumes/`).      |
| **Named or Anonymous**               | You can explicitly name volumes (`my-data`) or let Docker create one automatically.                |
| **Can be mounted read-write or read-only** | You control access level when mounting (`:ro` for read-only).                                      |
| **Independent of container lifecycle** | Deleting a container doesn’t delete the volume unless you remove it explicitly.                    |
| **Portable**                         | Can be backed up, copied, or used across environments.                                              |
| **Safe Defaults**                    | Volumes have good default permissions and are more secure than bind mounts.                        |



### Using postgres as database

#### `tmpfs` directories
Postgres needs to write data like process (PID) information, logs, and temporary files.
To allow this, we need to mount the following directories as `tmpfs` because the container is running in read-only mode:
- /run
- /tmp

#### volumes
- `data_postgres:/var/lib/postgresql/data`: Persists the database data across container restarts.

#### environment
- `POSTGRES_USER`: The username of the database user (default: `postgres` if not specified).
- `POSTGRES_PASSWORD`: The password of the database user (required).
- `POSTGRES_DB`: The name of the database (default: `POSTGRES_USER` if not specified).

### Using nginx-proxy as reverse proxy

When using the nginx-proxy as a reverse proxy, it is absolutly required to set the `VIRTUAL_HOST` environment variable
to the domain name of the web app in the environment variables of the web app container. 
This is necessary for the reverse proxy to forward the requests to the correct container.

Note: For local testing, the `VIRTUAL_HOST` environment variable can be set to `localhost`.

#### `tmpfs` directories
Nginx needs to write data like process (PID) information, logs, and temporary files.
To allow this, we need to mount the following directories as `tmpfs`:
- `/var/cache/nginx`
- `/var/run`
- `/tmp`

#### volumes
- `/var/run/docker.sock:/tmp/docker.sock:ro`: host docker daemon is made accessible to the container.
- `data_static:/home/app/src/app/static:ro`: the app's static files are mounted in a separate volume.
- `cache_nginx:/var/cache/nginx`: Persists NGINX's cache data, which improves performance by storing frequently accessed 
content across container restarts.
- `state_nginx:/etc/nginx`: Stores NGINX configuration files, SSL settings, and custom vhost definitions. Allows changes 
to persist and be shared between containers if needed.

In the productive environment, we use [acme-companion](https://github.com/nginx-proxy/acme-companion) to handle 
letsencrypt SSL certificate requests.

Therefore, we need some additional directories to be mounted as volumes, to which they share access to:
- `certs:/etc/nginx/certs:ro`: Provides read-only access to SSL/TLS certificates generated by the ACME companion, 
used by NGINX to serve HTTPS traffic.
- `html:/usr/share/nginx/html`: Required by the ACME companion to store HTTP challenge files during the Let's 
Encrypt certificate validation process.


- `vhost:/etc/nginx/vhost.d`: Stores auto-generated per-virtual-host configuration snippets, based on containers that 
define the `VIRTUAL_HOST` environment variable.

#### Connect uWSGI Upstream

If you would like to connect to uWSGI backend, set `VIRTUAL_PROTO=uwsgi` on the app container. 
Your backend container should then listen on a port rather than a socket and expose that port (`VIRTUAL_PORT`) e. g. 
default 3031 ([Source](https://github.com/nginx-proxy/nginx-proxy/tree/main/docs#virtual-hosts-and-ports)).

### Configure acme-companion for automated SSL certificate handling

The acme-companion is a separate service that is used to handle SSL certificate requests from letsencrypt. It also
automatically renews the certificates. The acme-companion is kind of a helper service for the nginx reverse proxy.

The acme-companion needs to have access to the same volumes as the nginx container.

#### volumes
- `certs:/etc/nginx/certs:rw`: Provides read-write access to SSL/TLS certificates generated by the ACME companion,
- `html:/usr/share/nginx/html`: Required by the ACME companion to store HTTP challenge files during the Let's Encrypt
challenge
- `/var/run/docker.sock:/var/run/docker.sock:ro`: host docker daemon is made accessible to the container.
- `/etc/acme.sh`: needs access to script file.

#### environment
- `DEFAULT_EMAIL`: The email address that needs to be provided to letsencrypt for certificate requests.

## Statistics with [GoAccess](https://hub.docker.com/r/allinurl/goaccess)
GoAccess is an open source real-time web log analyzer and interactive viewer.
It would require some changes in my nginx-proxy config. This is now the right moment to switch to the all-in-one solution caddy.
1) change to caddy
2) include goaccess on a stats html page 
