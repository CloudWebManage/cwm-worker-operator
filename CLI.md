# cwm-worker-operator cli

## CLI reference

<!-- start reference -->

### cwm-worker-operator

```
Usage: cwm-worker-operator [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  alerter
  cleaner
  clear-cacher
  cwm-api-volume-config-api-call
  deleter
  deployer
  disk-usage-updater
  get-cwm-api-volume-config
  get-cwm-updates
  initializer
  metrics-updater
  nodes-checker
  updater
  waiter
  web-ui
```

#### cwm-worker-operator initializer

```
Usage: cwm-worker-operator initializer [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  start_daemon
```

#### cwm-worker-operator initializer start_daemon

```
Usage: cwm-worker-operator initializer start_daemon [OPTIONS]

Options:
  --once
  --help  Show this message and exit.
```

#### cwm-worker-operator deployer

```
Usage: cwm-worker-operator deployer [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  deploy_worker
  start_daemon
```

#### cwm-worker-operator deployer start_daemon

```
Usage: cwm-worker-operator deployer start_daemon [OPTIONS]

Options:
  --once
  --help  Show this message and exit.
```

#### cwm-worker-operator deployer deploy_worker

```
Usage: cwm-worker-operator deployer deploy_worker [OPTIONS]

Options:
  --worker-id TEXT
  --debug
  --dry-run
  --help            Show this message and exit.
```

#### cwm-worker-operator waiter

```
Usage: cwm-worker-operator waiter [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  start_daemon
```

#### cwm-worker-operator waiter start_daemon

```
Usage: cwm-worker-operator waiter start_daemon [OPTIONS]

Options:
  --once
  --help  Show this message and exit.
```

#### cwm-worker-operator deleter

```
Usage: cwm-worker-operator deleter [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  delete
  start_daemon
```

#### cwm-worker-operator deleter start_daemon

```
Usage: cwm-worker-operator deleter start_daemon [OPTIONS]

Options:
  --once
  --help  Show this message and exit.
```

#### cwm-worker-operator deleter delete

```
Usage: cwm-worker-operator deleter delete [OPTIONS]

Options:
  --worker-id TEXT
  --hostname TEXT
  --deployment-timeout-string TEXT
  --with-metrics
  --help                          Show this message and exit.
```

#### cwm-worker-operator updater

```
Usage: cwm-worker-operator updater [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  start_daemon
```

#### cwm-worker-operator updater start_daemon

```
Usage: cwm-worker-operator updater start_daemon [OPTIONS]

Options:
  --once
  --help  Show this message and exit.
```

#### cwm-worker-operator metrics-updater

```
Usage: cwm-worker-operator metrics-updater [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  start_daemon
```

#### cwm-worker-operator metrics-updater start_daemon

```
Usage: cwm-worker-operator metrics-updater start_daemon [OPTIONS]

Options:
  --once
  --help  Show this message and exit.
```

#### cwm-worker-operator web-ui

```
Usage: cwm-worker-operator web-ui [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  start_daemon
```

#### cwm-worker-operator web-ui start_daemon

```
Usage: cwm-worker-operator web-ui start_daemon [OPTIONS]

Options:
  --help  Show this message and exit.
```

#### cwm-worker-operator disk-usage-updater

```
Usage: cwm-worker-operator disk-usage-updater [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  start_daemon
```

#### cwm-worker-operator disk-usage-updater start_daemon

```
Usage: cwm-worker-operator disk-usage-updater start_daemon 
           [OPTIONS]

Options:
  --once
  --help  Show this message and exit.
```

#### cwm-worker-operator alerter

```
Usage: cwm-worker-operator alerter [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  start_daemon
```

#### cwm-worker-operator alerter start_daemon

```
Usage: cwm-worker-operator alerter start_daemon [OPTIONS]

Options:
  --once
  --help  Show this message and exit.
```

#### cwm-worker-operator cleaner

```
Usage: cwm-worker-operator cleaner [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  start_daemon
```

#### cwm-worker-operator cleaner start_daemon

```
Usage: cwm-worker-operator cleaner start_daemon [OPTIONS]

Options:
  --once
  --help  Show this message and exit.
```

#### cwm-worker-operator nodes-checker

```
Usage: cwm-worker-operator nodes-checker [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  start_daemon
```

#### cwm-worker-operator nodes-checker start_daemon

```
Usage: cwm-worker-operator nodes-checker start_daemon [OPTIONS]

Options:
  --once
  --help  Show this message and exit.
```

#### cwm-worker-operator clear-cacher

```
Usage: cwm-worker-operator clear-cacher [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  start_daemon
```

#### cwm-worker-operator clear-cacher start_daemon

```
Usage: cwm-worker-operator clear-cacher start_daemon [OPTIONS]

Options:
  --once
  --help  Show this message and exit.
```

#### cwm-worker-operator cwm-api-volume-config-api-call

```
Usage: cwm-worker-operator cwm-api-volume-config-api-call [OPTIONS]
                                                          QUERY_PARAM
                                                          QUERY_VALUE

Options:
  --help  Show this message and exit.
```

#### cwm-worker-operator get-cwm-api-volume-config

```
Usage: cwm-worker-operator get-cwm-api-volume-config [OPTIONS]

Options:
  --force-update
  --hostname TEXT
  --worker-id TEXT
  --help            Show this message and exit.
```

#### cwm-worker-operator get-cwm-updates

```
Usage: cwm-worker-operator get-cwm-updates [OPTIONS]

Options:
  --from-before-seconds TEXT
  --from-datetime TEXT
  --help                      Show this message and exit.
```
<!-- end reference -->
