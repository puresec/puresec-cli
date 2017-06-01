# puresec-generate-roles

A CLI tool for creating cloud roles with least privilege permissions using static code analysis.

## Development

```bash
pip install -r requirements.txt requirements/*
nosetests -c nose.cfg puresec_generate_roles/
```

## Usage

```bash
pip install -r requirements.txt requirements/<depending on your needs>.txt
bin/gen-roles --help
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
