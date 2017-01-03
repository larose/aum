# AUM

This project is a responsive website for the schedule of the
Association de Ultimate de Montréal (AUM) games. It is hosted at
http://aum.mathieularose.com

This is a static website generated every hour based on the data at
http://www.montrealultimate.ca


# Development

## Dependencies

- Python 3
- Virtualenv

## Setup

Generate the virtual environment: `make env`

## Edit-compile-test loop

In a terminal:

1. Start an http server: `make start`

In another terminal:

1. Activate the virtual environment: `source env/bin/activate`
2. Edit
3. Compile: `make generate`
4. Test: open your browser at `http://127.0.0.1:8000`
5. Go to step 2

If you don't want to fetch the pages from
http://www.montrealultimate.ca every time you generate the website,
replace step 3 with `USE_CACHE=y make generate`. It will use a local
cache.

# Operations

## Setup

On dokku:

```
$ dokku apps:create aum
$ dokku domains:add aum aum.mathieularose.com
$ dokku config:set aum BUILDPACK_URL=https://github.com/larose/buildpack-nginx
```

```
$ dokku apps:create aum-updater
$ dokku config:set aum-updater GIT_AUTHOR_NAME=aum-updater GIT_COMMITTER_NAME=aum-updater GIT_AUTHOR_EMAIL=dokku@d1.mathieularose.com GIT_COMMITTER_EMAIL=dokku@d1.mathieularose.com
$ ssh-keygen -t rsa -b 4096 -C "ubuntu@d1.mathieularose.com"
$ ssh-keys:add /home/ubuntu/.ssh/id_rsa
$ sudo dokku ssh-keys:add ubuntu ~/.ssh/id_rsa.pub
$ dokku config:set aum-updater SSH_PRIVATE_KEY="`cat ~/.ssh/id_rsa | tr '\n' '#'`"
$ dokku config:set aum-updater SSH_PUBLIC_KEY="`cat ~/.ssh/id_rsa.pub | tr '\n' '#'`"
$ dokku ps:scale aum-updater web=0 cron=1
```

```
$ sudo su dokku
$ crontab -e
$ # @hourly dokku enter aum-updater cron make deploy-from-updater
```

On local machine:

```
$ git remote add d1 dokku@d1.mathieularose.com:aum-updater
```


## Manual deployment

```
$ make deploy
```
