# cwm-worker-operator cli

## CLI reference

<!-- start reference -->

### cwm-worker-operator

```
Usage: cwm-worker-operator [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  alerter                         Sends alerts (to Slack)
  cleaner                         Cleanup unused cache data from nodes
  clear-cacher                    Handles requests for Nginx clear cache from
                                  users

  cwm-api-volume-config-api-call  Make a low-level API call to get cwm
                                  instance volume configuration

  deleter                         Deletes worker deployments
  deployer                        Deploys workers
  disk-usage-updater              Collects disk usage data for workers
  get-cwm-api-volume-config       Make an operator api call to get instance
                                  volume config from cache

  get-cwm-updates                 Make a low-level CWM api call to get cwm
                                  instance updates in the given time-range

  initializer                     Initializes requests to deploy workers (the
                                  first step in deployment process)

  metrics-updater                 Aggregates metric data from workers
  nas-checker                     Checks health of NAS servers mounting from
                                  worker nodes
                                  
                                  It iterates over all cluster worker nodes
                                  and mounts each NAS server

  nodes-checker                   Checks nodes and updates DNS records
                                  accordingly
                                  
                                  It doesn't actually do any healthchecks
                                  itself, it just updates DNS records for all
                                  cluster worker nodes. Each worker node also
                                  gets an AWS Route53 healthcheck which does
                                  the actual healthcheck and removes it from
                                  DNS if it fails. The healthchecks check cwm-
                                  worker-ingress /healthz path, so if the
                                  ingress stops responding the node is removed
                                  from DNS.
                                  
                                  In addition to the DNS healthchecks, the
                                  cwm-worker-ingress checks redis key
                                  node:healthy, if key is missing the /healthz
                                  path returns an error. nodes_checker updates
                                  this redis key to true for all worker nodes
                                  and to false for any nodes which are not
                                  currently listed as worker nodes - so nodes
                                  which are removed will instantly stop
                                  serving.

  redis-cleaner                   Cleanup Redis keys
  send-agg-metrics                Send aggregated metrics to CWM api for
                                  debugging

  updater                         Initiates updates for workers, also sends
                                  aggregated metrics to CWM

  waiter                          Waits for deployed workers to be available
  web-ui                          A web interface for debugging
  workers-checker                 Check workers and update status in Redis
```

#### cwm-worker-operator initializer

```
Usage: cwm-worker-operator initializer [OPTIONS] COMMAND [ARGS]...

  Initializes requests to deploy workers (the first step in deployment
  process)

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

  Deploys workers

Options:
  --help  Show this message and exit.

Commands:
  deploy_worker  Manually deploy a worker for debugging
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

  Manually deploy a worker for debugging

Options:
  --worker-id TEXT
  --debug
  --dry-run
  --help            Show this message and exit.
```

#### cwm-worker-operator waiter

```
Usage: cwm-worker-operator waiter [OPTIONS] COMMAND [ARGS]...

  Waits for deployed workers to be available

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

  Deletes worker deployments

Options:
  --help  Show this message and exit.

Commands:
  delete        Manually delete a worker for debugging
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

  Manually delete a worker for debugging

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

  Initiates updates for workers, also sends aggregated metrics to CWM

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

  Aggregates metric data from workers

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

  A web interface for debugging

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

  Collects disk usage data for workers

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

  Sends alerts (to Slack)

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

  Cleanup unused cache data from nodes

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

  Checks nodes and updates DNS records accordingly

  It doesn't actually do any healthchecks itself, it just updates DNS
  records for all cluster worker nodes. Each worker node also gets an AWS
  Route53 healthcheck which does the actual healthcheck and removes it from
  DNS if it fails. The healthchecks check cwm-worker-ingress /healthz path,
  so if the ingress stops responding the node is removed from DNS.

  In addition to the DNS healthchecks, the cwm-worker-ingress checks redis
  key node:healthy, if key is missing the /healthz path returns an error.
  nodes_checker updates this redis key to true for all worker nodes and to
  false for any nodes which are not currently listed as worker nodes - so
  nodes which are removed will instantly stop serving.

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

  Handles requests for Nginx clear cache from users

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

#### cwm-worker-operator nas-checker

```
Usage: cwm-worker-operator nas-checker [OPTIONS] COMMAND [ARGS]...

  Checks health of NAS servers mounting from worker nodes

  It iterates over all cluster worker nodes and mounts each NAS server

Options:
  --help  Show this message and exit.

Commands:
  start_daemon
```

#### cwm-worker-operator nas-checker start_daemon

```
Usage: cwm-worker-operator nas-checker start_daemon [OPTIONS]

Options:
  --once
  --help  Show this message and exit.
```

#### cwm-worker-operator redis-cleaner

```
Usage: cwm-worker-operator redis-cleaner [OPTIONS] COMMAND [ARGS]...

  Cleanup Redis keys

Options:
  --help  Show this message and exit.

Commands:
  start_daemon
```

#### cwm-worker-operator redis-cleaner start_daemon

```
Usage: cwm-worker-operator redis-cleaner start_daemon [OPTIONS]

Options:
  --once
  --help  Show this message and exit.
```

#### cwm-worker-operator workers-checker

```
Usage: cwm-worker-operator workers-checker [OPTIONS] COMMAND [ARGS]...

  Check workers and update status in Redis

Options:
  --help  Show this message and exit.

Commands:
  start_daemon
```

#### cwm-worker-operator workers-checker start_daemon

```
Usage: cwm-worker-operator workers-checker start_daemon [OPTIONS]

Options:
  --once
  --help  Show this message and exit.
```

#### cwm-worker-operator cwm-api-volume-config-api-call

```
Usage: cwm-worker-operator cwm-api-volume-config-api-call [OPTIONS]
                                                          QUERY_PARAM
                                                          QUERY_VALUE

  Make a low-level API call to get cwm instance volume configuration

  Supported QUERY_PARAM values: id / hostname

Options:
  --help  Show this message and exit.
```

#### cwm-worker-operator get-cwm-api-volume-config

```
Usage: cwm-worker-operator get-cwm-api-volume-config [OPTIONS]

  Make an operator api call to get instance volume config from cache

Options:
  --force-update    Ignore the cache and force update from CWM api
  --hostname TEXT
  --worker-id TEXT
  --help            Show this message and exit.
```

#### cwm-worker-operator get-cwm-updates

```
Usage: cwm-worker-operator get-cwm-updates [OPTIONS]

  Make a low-level CWM api call to get cwm instance updates in the given
  time-range

Options:
  --from-before-seconds TEXT
  --from-datetime TEXT
  --help                      Show this message and exit.
```

#### cwm-worker-operator send-agg-metrics

```
Usage: cwm-worker-operator send-agg-metrics [OPTIONS] WORKER_ID MINUTES_JSON

  Send aggregated metrics to CWM api for debugging

  Example minutes_json data ("t": "%Y%m%d%H%M%S"):
  [
      {
          "t": "20210825214533",
          "disk_usage_bytes": 100,
          "bytes_in": 200,
          "bytes_out": 300,
          "num_requests_in": 5,
          "num_requests_out": 10,
          "num_requests_misc": 15,
          "sum_cpu_seconds": 50,
          "ram_limit_bytes": 100
      }
  ]

Options:
  --help  Show this message and exit.
```
<!-- end reference -->
