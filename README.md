# least-privileges

A CLI tool for creating IAM roles with least privilege permissions using static code analysis.

## Development

```bash
pip install -r requirements.txt requirements/*
nosetests -c nose.cfg least_privileges/
```

## Usage

```bash
pip install -r requirements.txt requirements/<depending on your needs>.txt
bin/lp --help
```

### Serverless

In your Serverless project's root directory:

```bash
npm install --save-dev serverless-dumpconfig
```

And add the plugin to your `serverless.yml`:

```yaml
plugins:
  - serverless-dumpconfig
```
