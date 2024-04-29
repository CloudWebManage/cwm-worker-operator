"""
Streams / aggregates data from a Kafka topic
This daemon can run multiple instances in parallel, each instance handling a different topic.
"""
import os
import json
import functools
import subprocess
from textwrap import dedent

from confluent_kafka import Consumer

from cwm_worker_operator.daemon import Daemon
from cwm_worker_operator import config, common, logs
from cwm_worker_operator.domains_config import DomainsConfig


MINIO_TENANT_MAIN_AUDIT_LOGS_TOPIC = 'minio-tenant-main-audit-logs'
DEPLOYMENT_API_METRICS_BASE_DATA = {
    'bytes_in': 0,
    'bytes_out': 0,
    'num_requests_in': 0,
    'num_requests_out': 0,
    'num_requests_misc': 0,
}


def get_request_type(name):
    if name in ['WebUpload', 'PutObject', 'DeleteObject']:
        return 'in'
    elif name in ['WebDownload', 'GetObject']:
        return 'out'
    else:
        return 'misc'


def process_minio_tenant_main_audit_logs_update_agg_data(agg_data, namespace_name, request_type, tx, rx):
    if namespace_name not in agg_data:
        logs.debug(f"process_minio_tenant_main_audit_logs: {namespace_name}", 10)
        agg_data[namespace_name] = DEPLOYMENT_API_METRICS_BASE_DATA.copy()
    agg_data[namespace_name][f'bytes_in'] += int(rx)
    agg_data[namespace_name][f'bytes_out'] += int(tx)
    agg_data[namespace_name][f'num_requests_{request_type}'] += 1


def process_minio_tenant_main_audit_logs(data, agg_data, domains_config):
    data_api = data.get('api', {})
    bucket = data_api.get('bucket')
    if bucket:
        namespace_name = common.get_namespace_name_from_bucket_name(bucket)
        if namespace_name:
            tx = data_api.get('tx') or 0
            rx = data_api.get('rx') or 0
            request_type = get_request_type(data_api.get('name'))
            process_minio_tenant_main_audit_logs_update_agg_data(agg_data, namespace_name, request_type, tx, rx)
            logs.debug('process_minio_tenant_main_audit_logs (minio)', 10, data_api=data_api)
    elif data.get('message') and (data.get('ident') or '').startswith('nginx-'):
        message = json.loads(data['message'])
        host = message.get('host')
        upstream_cache_status = message.get('upstream_cache_status')
        if host and upstream_cache_status == 'HIT':
            try:
                worker_id = domains_config.get_cwm_api_volume_config(hostname=host).id
            except:
                worker_id = None
            if worker_id:
                namespace_name = common.get_namespace_name_from_worker_id(worker_id)
                if namespace_name:
                    request = message.get('request') or ''
                    request_type = 'out' if request.startswith('GET ') else 'misc'
                    tx = message.get('bytes_sent') or 0
                    rx = message.get('request_length') or 0
                    process_minio_tenant_main_audit_logs_update_agg_data(agg_data, namespace_name, request_type, tx, rx)
                    logs.debug('process_minio_tenant_main_audit_logs (cdn)', 10, message=message)


def commit_minio_tenant_main_audit_logs(domains_config, agg_data):
    logs.debug(f"commit_minio_tenant_main_audit_logs: {agg_data}", 10)
    for namespace_name, data in agg_data.items():
        domains_config.update_deployment_api_metrics(namespace_name, data)
        domains_config.set_deployment_last_action(namespace_name)


def process_data(topic, data, agg_data, domains_config):
    if topic == MINIO_TENANT_MAIN_AUDIT_LOGS_TOPIC:
        process_minio_tenant_main_audit_logs(data, agg_data, domains_config)
    else:
        raise NotImplementedError(f"topic {topic} is not supported")


def commit(topic, consumer, domains_config, agg_data, no_kafka_commit=False):
    if topic == MINIO_TENANT_MAIN_AUDIT_LOGS_TOPIC:
        commit_minio_tenant_main_audit_logs(domains_config, agg_data)
    else:
        raise NotImplementedError(f"topic {topic} is not supported")
    if not no_kafka_commit:
        consumer.commit()


def delete_records(topic, latest_partition_offset):
    partitions = [
        {'topic': topic, 'partition': p, 'offset': o}
        for p, o in latest_partition_offset.items()
    ]
    if len(partitions) > 0:
        offset_json = json.dumps({'partitions': partitions, 'version': 1})
        logs.debug(f"Deleting records: {offset_json}", 10)
        subprocess.check_call([
            'kubectl', 'exec', '-n', config.KAFKA_STREAMER_POD_NAMESPACE, config.KAFKA_STREAMER_POD_NAME, '--', 'bash', '-c', dedent(f'''
                TMPFILE=$(mktemp) &&\
                echo '{offset_json}' > $TMPFILE &&\
                bin/kafka-delete-records.sh --bootstrap-server localhost:9092 --offset-json-file $TMPFILE &&\
                rm $TMPFILE
            ''').strip()
        ], env={**os.environ, 'DEBUG': ''})


def run_single_iteration(domains_config: DomainsConfig, topic, daemon, no_kafka_commit=False, no_kafka_delete=False, **_):
    start_time = common.now()
    assert topic, "topic is required"
    assert config.KAFKA_STREAMER_BOOTSTRAP_SERVERS
    logs.debug(f"running iteration for topic: {topic}", 10)
    consumer = Consumer({
        'bootstrap.servers': config.KAFKA_STREAMER_BOOTSTRAP_SERVERS,
        'group.id': config.KAFKA_STREAMER_OPERATOR_GROUP_ID,
        **config.KAFKA_STREAMER_CONSUMER_CONFIG
    })
    consumer.subscribe([topic])
    latest_partition_offset = {}
    try:
        agg_data = {}
        commit_ = functools.partial(commit, topic, consumer, domains_config, agg_data, no_kafka_commit=no_kafka_commit)
        while (common.now() - start_time).total_seconds() < config.KAFKA_STREAMER_POLL_TIME_SECONDS and not daemon.terminate_requested:
            msg = consumer.poll(timeout=config.KAFKA_STREAMER_CONSUMER_POLL_TIMEOUT_SECONDS)
            if msg is None:
                logs.debug("Waiting for messages...", 10)
                commit_()
            elif msg.error():
                raise Exception(f"Message ERROR: {msg.error()}")
            else:
                offset = msg.offset()
                partition = msg.partition()
                latest_partition_offset[partition] = offset
                data = json.loads(msg.value())
                process_data(topic, data, agg_data, domains_config)
        commit_()
    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()
    if not no_kafka_delete:
        delete_records(topic, latest_partition_offset)


def start_daemon(once=False, domains_config=None, topic=None, no_kafka_commit=False, no_kafka_delete=False):
    if not topic:
        topic = config.KAFKA_STREAMER_TOPIC
    assert topic
    Daemon(
        name=f"kafka_streamer_{topic}",
        sleep_time_between_iterations_seconds=config.KAFKA_STREAMER_SLEEP_TIME_BETWEEN_ITERATIONS_SECONDS,
        domains_config=domains_config,
        run_single_iteration_callback=run_single_iteration,
        run_single_iteration_extra_kwargs={'topic': topic, 'no_kafka_commit': no_kafka_commit, 'no_kafka_delete': no_kafka_delete},
    ).start(
        once=once,
        with_prometheus=False,
    )
