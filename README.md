Fetch all test failure output from a GoCD pipeline

```
GoCD credentials must be stored as shell environment variables:

  export GOCD_USER=my_username GOCD_PASSWORD=my_password

Usage:
  gocd-get-test-failures BUILD [--format=FORMAT] [--stage=STAGE] [--job=JOB]
  gocd-get-test-failures --show-pipelines

Example:
  export GOCD_USER=my_username GOCD_PASSWORD=my_password
  gocd-get-test-failures some-pipeline/2275

Options:
  --format=FORMAT   Output format: org or json [default: json].
  --show-pipelines  Show stage/job names for known pipelines.
  --stage=STAGE     Set stage name for pipeline.
  --job=JOB         Set job name for pipeline.
  -h --help         Show this help.
```
