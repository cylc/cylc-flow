from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class PbMeta(_message.Message):
    __slots__ = ("title", "description", "URL", "user_defined")
    TITLE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    URL_FIELD_NUMBER: _ClassVar[int]
    USER_DEFINED_FIELD_NUMBER: _ClassVar[int]
    title: str
    description: str
    URL: str
    user_defined: str
    def __init__(self, title: _Optional[str] = ..., description: _Optional[str] = ..., URL: _Optional[str] = ..., user_defined: _Optional[str] = ...) -> None: ...

class PbTimeZone(_message.Message):
    __slots__ = ("hours", "minutes", "string_basic", "string_extended")
    HOURS_FIELD_NUMBER: _ClassVar[int]
    MINUTES_FIELD_NUMBER: _ClassVar[int]
    STRING_BASIC_FIELD_NUMBER: _ClassVar[int]
    STRING_EXTENDED_FIELD_NUMBER: _ClassVar[int]
    hours: int
    minutes: int
    string_basic: str
    string_extended: str
    def __init__(self, hours: _Optional[int] = ..., minutes: _Optional[int] = ..., string_basic: _Optional[str] = ..., string_extended: _Optional[str] = ...) -> None: ...

class PbTaskProxyRefs(_message.Message):
    __slots__ = ("task_proxies",)
    TASK_PROXIES_FIELD_NUMBER: _ClassVar[int]
    task_proxies: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, task_proxies: _Optional[_Iterable[str]] = ...) -> None: ...

class PbWorkflow(_message.Message):
    __slots__ = ("stamp", "id", "name", "status", "host", "port", "owner", "tasks", "families", "edges", "api_version", "cylc_version", "last_updated", "meta", "newest_active_cycle_point", "oldest_active_cycle_point", "reloaded", "run_mode", "cycling_mode", "state_totals", "workflow_log_dir", "time_zone_info", "tree_depth", "job_log_names", "ns_def_order", "states", "task_proxies", "family_proxies", "status_msg", "is_held_total", "jobs", "pub_port", "broadcasts", "is_queued_total", "latest_state_tasks", "pruned", "is_runahead_total", "states_updated", "n_edge_distance", "log_records")
    class StateTotalsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: int
        def __init__(self, key: _Optional[str] = ..., value: _Optional[int] = ...) -> None: ...
    class LatestStateTasksEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: PbTaskProxyRefs
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[PbTaskProxyRefs, _Mapping]] = ...) -> None: ...
    STAMP_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    HOST_FIELD_NUMBER: _ClassVar[int]
    PORT_FIELD_NUMBER: _ClassVar[int]
    OWNER_FIELD_NUMBER: _ClassVar[int]
    TASKS_FIELD_NUMBER: _ClassVar[int]
    FAMILIES_FIELD_NUMBER: _ClassVar[int]
    EDGES_FIELD_NUMBER: _ClassVar[int]
    API_VERSION_FIELD_NUMBER: _ClassVar[int]
    CYLC_VERSION_FIELD_NUMBER: _ClassVar[int]
    LAST_UPDATED_FIELD_NUMBER: _ClassVar[int]
    META_FIELD_NUMBER: _ClassVar[int]
    NEWEST_ACTIVE_CYCLE_POINT_FIELD_NUMBER: _ClassVar[int]
    OLDEST_ACTIVE_CYCLE_POINT_FIELD_NUMBER: _ClassVar[int]
    RELOADED_FIELD_NUMBER: _ClassVar[int]
    RUN_MODE_FIELD_NUMBER: _ClassVar[int]
    CYCLING_MODE_FIELD_NUMBER: _ClassVar[int]
    STATE_TOTALS_FIELD_NUMBER: _ClassVar[int]
    WORKFLOW_LOG_DIR_FIELD_NUMBER: _ClassVar[int]
    TIME_ZONE_INFO_FIELD_NUMBER: _ClassVar[int]
    TREE_DEPTH_FIELD_NUMBER: _ClassVar[int]
    JOB_LOG_NAMES_FIELD_NUMBER: _ClassVar[int]
    NS_DEF_ORDER_FIELD_NUMBER: _ClassVar[int]
    STATES_FIELD_NUMBER: _ClassVar[int]
    TASK_PROXIES_FIELD_NUMBER: _ClassVar[int]
    FAMILY_PROXIES_FIELD_NUMBER: _ClassVar[int]
    STATUS_MSG_FIELD_NUMBER: _ClassVar[int]
    IS_HELD_TOTAL_FIELD_NUMBER: _ClassVar[int]
    JOBS_FIELD_NUMBER: _ClassVar[int]
    PUB_PORT_FIELD_NUMBER: _ClassVar[int]
    BROADCASTS_FIELD_NUMBER: _ClassVar[int]
    IS_QUEUED_TOTAL_FIELD_NUMBER: _ClassVar[int]
    LATEST_STATE_TASKS_FIELD_NUMBER: _ClassVar[int]
    PRUNED_FIELD_NUMBER: _ClassVar[int]
    IS_RUNAHEAD_TOTAL_FIELD_NUMBER: _ClassVar[int]
    STATES_UPDATED_FIELD_NUMBER: _ClassVar[int]
    N_EDGE_DISTANCE_FIELD_NUMBER: _ClassVar[int]
    LOG_RECORDS_FIELD_NUMBER: _ClassVar[int]
    stamp: str
    id: str
    name: str
    status: str
    host: str
    port: int
    owner: str
    tasks: _containers.RepeatedScalarFieldContainer[str]
    families: _containers.RepeatedScalarFieldContainer[str]
    edges: PbEdges
    api_version: int
    cylc_version: str
    last_updated: float
    meta: PbMeta
    newest_active_cycle_point: str
    oldest_active_cycle_point: str
    reloaded: bool
    run_mode: str
    cycling_mode: str
    state_totals: _containers.ScalarMap[str, int]
    workflow_log_dir: str
    time_zone_info: PbTimeZone
    tree_depth: int
    job_log_names: _containers.RepeatedScalarFieldContainer[str]
    ns_def_order: _containers.RepeatedScalarFieldContainer[str]
    states: _containers.RepeatedScalarFieldContainer[str]
    task_proxies: _containers.RepeatedScalarFieldContainer[str]
    family_proxies: _containers.RepeatedScalarFieldContainer[str]
    status_msg: str
    is_held_total: int
    jobs: _containers.RepeatedScalarFieldContainer[str]
    pub_port: int
    broadcasts: str
    is_queued_total: int
    latest_state_tasks: _containers.MessageMap[str, PbTaskProxyRefs]
    pruned: bool
    is_runahead_total: int
    states_updated: bool
    n_edge_distance: int
    log_records: _containers.RepeatedCompositeFieldContainer[PbLogRecord]
    def __init__(self, stamp: _Optional[str] = ..., id: _Optional[str] = ..., name: _Optional[str] = ..., status: _Optional[str] = ..., host: _Optional[str] = ..., port: _Optional[int] = ..., owner: _Optional[str] = ..., tasks: _Optional[_Iterable[str]] = ..., families: _Optional[_Iterable[str]] = ..., edges: _Optional[_Union[PbEdges, _Mapping]] = ..., api_version: _Optional[int] = ..., cylc_version: _Optional[str] = ..., last_updated: _Optional[float] = ..., meta: _Optional[_Union[PbMeta, _Mapping]] = ..., newest_active_cycle_point: _Optional[str] = ..., oldest_active_cycle_point: _Optional[str] = ..., reloaded: bool = ..., run_mode: _Optional[str] = ..., cycling_mode: _Optional[str] = ..., state_totals: _Optional[_Mapping[str, int]] = ..., workflow_log_dir: _Optional[str] = ..., time_zone_info: _Optional[_Union[PbTimeZone, _Mapping]] = ..., tree_depth: _Optional[int] = ..., job_log_names: _Optional[_Iterable[str]] = ..., ns_def_order: _Optional[_Iterable[str]] = ..., states: _Optional[_Iterable[str]] = ..., task_proxies: _Optional[_Iterable[str]] = ..., family_proxies: _Optional[_Iterable[str]] = ..., status_msg: _Optional[str] = ..., is_held_total: _Optional[int] = ..., jobs: _Optional[_Iterable[str]] = ..., pub_port: _Optional[int] = ..., broadcasts: _Optional[str] = ..., is_queued_total: _Optional[int] = ..., latest_state_tasks: _Optional[_Mapping[str, PbTaskProxyRefs]] = ..., pruned: bool = ..., is_runahead_total: _Optional[int] = ..., states_updated: bool = ..., n_edge_distance: _Optional[int] = ..., log_records: _Optional[_Iterable[_Union[PbLogRecord, _Mapping]]] = ...) -> None: ...

class PbLogRecord(_message.Message):
    __slots__ = ("level", "message")
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    level: str
    message: str
    def __init__(self, level: _Optional[str] = ..., message: _Optional[str] = ...) -> None: ...

class PbRuntime(_message.Message):
    __slots__ = ("platform", "script", "init_script", "env_script", "err_script", "exit_script", "pre_script", "post_script", "work_sub_dir", "execution_polling_intervals", "execution_retry_delays", "execution_time_limit", "submission_polling_intervals", "submission_retry_delays", "directives", "environment", "outputs", "completion", "run_mode")
    PLATFORM_FIELD_NUMBER: _ClassVar[int]
    SCRIPT_FIELD_NUMBER: _ClassVar[int]
    INIT_SCRIPT_FIELD_NUMBER: _ClassVar[int]
    ENV_SCRIPT_FIELD_NUMBER: _ClassVar[int]
    ERR_SCRIPT_FIELD_NUMBER: _ClassVar[int]
    EXIT_SCRIPT_FIELD_NUMBER: _ClassVar[int]
    PRE_SCRIPT_FIELD_NUMBER: _ClassVar[int]
    POST_SCRIPT_FIELD_NUMBER: _ClassVar[int]
    WORK_SUB_DIR_FIELD_NUMBER: _ClassVar[int]
    EXECUTION_POLLING_INTERVALS_FIELD_NUMBER: _ClassVar[int]
    EXECUTION_RETRY_DELAYS_FIELD_NUMBER: _ClassVar[int]
    EXECUTION_TIME_LIMIT_FIELD_NUMBER: _ClassVar[int]
    SUBMISSION_POLLING_INTERVALS_FIELD_NUMBER: _ClassVar[int]
    SUBMISSION_RETRY_DELAYS_FIELD_NUMBER: _ClassVar[int]
    DIRECTIVES_FIELD_NUMBER: _ClassVar[int]
    ENVIRONMENT_FIELD_NUMBER: _ClassVar[int]
    OUTPUTS_FIELD_NUMBER: _ClassVar[int]
    COMPLETION_FIELD_NUMBER: _ClassVar[int]
    RUN_MODE_FIELD_NUMBER: _ClassVar[int]
    platform: str
    script: str
    init_script: str
    env_script: str
    err_script: str
    exit_script: str
    pre_script: str
    post_script: str
    work_sub_dir: str
    execution_polling_intervals: str
    execution_retry_delays: str
    execution_time_limit: str
    submission_polling_intervals: str
    submission_retry_delays: str
    directives: str
    environment: str
    outputs: str
    completion: str
    run_mode: str
    def __init__(self, platform: _Optional[str] = ..., script: _Optional[str] = ..., init_script: _Optional[str] = ..., env_script: _Optional[str] = ..., err_script: _Optional[str] = ..., exit_script: _Optional[str] = ..., pre_script: _Optional[str] = ..., post_script: _Optional[str] = ..., work_sub_dir: _Optional[str] = ..., execution_polling_intervals: _Optional[str] = ..., execution_retry_delays: _Optional[str] = ..., execution_time_limit: _Optional[str] = ..., submission_polling_intervals: _Optional[str] = ..., submission_retry_delays: _Optional[str] = ..., directives: _Optional[str] = ..., environment: _Optional[str] = ..., outputs: _Optional[str] = ..., completion: _Optional[str] = ..., run_mode: _Optional[str] = ...) -> None: ...

class PbJob(_message.Message):
    __slots__ = ("stamp", "id", "submit_num", "state", "task_proxy", "submitted_time", "started_time", "finished_time", "job_id", "job_runner_name", "execution_time_limit", "platform", "job_log_dir", "name", "cycle_point", "messages", "runtime", "estimated_finish_time")
    STAMP_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    SUBMIT_NUM_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    TASK_PROXY_FIELD_NUMBER: _ClassVar[int]
    SUBMITTED_TIME_FIELD_NUMBER: _ClassVar[int]
    STARTED_TIME_FIELD_NUMBER: _ClassVar[int]
    FINISHED_TIME_FIELD_NUMBER: _ClassVar[int]
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    JOB_RUNNER_NAME_FIELD_NUMBER: _ClassVar[int]
    EXECUTION_TIME_LIMIT_FIELD_NUMBER: _ClassVar[int]
    PLATFORM_FIELD_NUMBER: _ClassVar[int]
    JOB_LOG_DIR_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    CYCLE_POINT_FIELD_NUMBER: _ClassVar[int]
    MESSAGES_FIELD_NUMBER: _ClassVar[int]
    RUNTIME_FIELD_NUMBER: _ClassVar[int]
    ESTIMATED_FINISH_TIME_FIELD_NUMBER: _ClassVar[int]
    stamp: str
    id: str
    submit_num: int
    state: str
    task_proxy: str
    submitted_time: str
    started_time: str
    finished_time: str
    job_id: str
    job_runner_name: str
    execution_time_limit: float
    platform: str
    job_log_dir: str
    name: str
    cycle_point: str
    messages: _containers.RepeatedScalarFieldContainer[str]
    runtime: PbRuntime
    estimated_finish_time: str
    def __init__(self, stamp: _Optional[str] = ..., id: _Optional[str] = ..., submit_num: _Optional[int] = ..., state: _Optional[str] = ..., task_proxy: _Optional[str] = ..., submitted_time: _Optional[str] = ..., started_time: _Optional[str] = ..., finished_time: _Optional[str] = ..., job_id: _Optional[str] = ..., job_runner_name: _Optional[str] = ..., execution_time_limit: _Optional[float] = ..., platform: _Optional[str] = ..., job_log_dir: _Optional[str] = ..., name: _Optional[str] = ..., cycle_point: _Optional[str] = ..., messages: _Optional[_Iterable[str]] = ..., runtime: _Optional[_Union[PbRuntime, _Mapping]] = ..., estimated_finish_time: _Optional[str] = ...) -> None: ...

class PbTask(_message.Message):
    __slots__ = ("stamp", "id", "name", "meta", "mean_elapsed_time", "depth", "proxies", "namespace", "parents", "first_parent", "runtime")
    STAMP_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    META_FIELD_NUMBER: _ClassVar[int]
    MEAN_ELAPSED_TIME_FIELD_NUMBER: _ClassVar[int]
    DEPTH_FIELD_NUMBER: _ClassVar[int]
    PROXIES_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    PARENTS_FIELD_NUMBER: _ClassVar[int]
    FIRST_PARENT_FIELD_NUMBER: _ClassVar[int]
    RUNTIME_FIELD_NUMBER: _ClassVar[int]
    stamp: str
    id: str
    name: str
    meta: PbMeta
    mean_elapsed_time: float
    depth: int
    proxies: _containers.RepeatedScalarFieldContainer[str]
    namespace: _containers.RepeatedScalarFieldContainer[str]
    parents: _containers.RepeatedScalarFieldContainer[str]
    first_parent: str
    runtime: PbRuntime
    def __init__(self, stamp: _Optional[str] = ..., id: _Optional[str] = ..., name: _Optional[str] = ..., meta: _Optional[_Union[PbMeta, _Mapping]] = ..., mean_elapsed_time: _Optional[float] = ..., depth: _Optional[int] = ..., proxies: _Optional[_Iterable[str]] = ..., namespace: _Optional[_Iterable[str]] = ..., parents: _Optional[_Iterable[str]] = ..., first_parent: _Optional[str] = ..., runtime: _Optional[_Union[PbRuntime, _Mapping]] = ...) -> None: ...

class PbPollTask(_message.Message):
    __slots__ = ("local_proxy", "workflow", "remote_proxy", "req_state", "graph_string")
    LOCAL_PROXY_FIELD_NUMBER: _ClassVar[int]
    WORKFLOW_FIELD_NUMBER: _ClassVar[int]
    REMOTE_PROXY_FIELD_NUMBER: _ClassVar[int]
    REQ_STATE_FIELD_NUMBER: _ClassVar[int]
    GRAPH_STRING_FIELD_NUMBER: _ClassVar[int]
    local_proxy: str
    workflow: str
    remote_proxy: str
    req_state: str
    graph_string: str
    def __init__(self, local_proxy: _Optional[str] = ..., workflow: _Optional[str] = ..., remote_proxy: _Optional[str] = ..., req_state: _Optional[str] = ..., graph_string: _Optional[str] = ...) -> None: ...

class PbCondition(_message.Message):
    __slots__ = ("task_proxy", "expr_alias", "req_state", "satisfied", "message")
    TASK_PROXY_FIELD_NUMBER: _ClassVar[int]
    EXPR_ALIAS_FIELD_NUMBER: _ClassVar[int]
    REQ_STATE_FIELD_NUMBER: _ClassVar[int]
    SATISFIED_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    task_proxy: str
    expr_alias: str
    req_state: str
    satisfied: bool
    message: str
    def __init__(self, task_proxy: _Optional[str] = ..., expr_alias: _Optional[str] = ..., req_state: _Optional[str] = ..., satisfied: bool = ..., message: _Optional[str] = ...) -> None: ...

class PbPrerequisite(_message.Message):
    __slots__ = ("expression", "conditions", "cycle_points", "satisfied")
    EXPRESSION_FIELD_NUMBER: _ClassVar[int]
    CONDITIONS_FIELD_NUMBER: _ClassVar[int]
    CYCLE_POINTS_FIELD_NUMBER: _ClassVar[int]
    SATISFIED_FIELD_NUMBER: _ClassVar[int]
    expression: str
    conditions: _containers.RepeatedCompositeFieldContainer[PbCondition]
    cycle_points: _containers.RepeatedScalarFieldContainer[str]
    satisfied: bool
    def __init__(self, expression: _Optional[str] = ..., conditions: _Optional[_Iterable[_Union[PbCondition, _Mapping]]] = ..., cycle_points: _Optional[_Iterable[str]] = ..., satisfied: bool = ...) -> None: ...

class PbOutput(_message.Message):
    __slots__ = ("label", "message", "satisfied", "time")
    LABEL_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    SATISFIED_FIELD_NUMBER: _ClassVar[int]
    TIME_FIELD_NUMBER: _ClassVar[int]
    label: str
    message: str
    satisfied: bool
    time: float
    def __init__(self, label: _Optional[str] = ..., message: _Optional[str] = ..., satisfied: bool = ..., time: _Optional[float] = ...) -> None: ...

class PbTrigger(_message.Message):
    __slots__ = ("id", "label", "message", "satisfied", "time")
    ID_FIELD_NUMBER: _ClassVar[int]
    LABEL_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    SATISFIED_FIELD_NUMBER: _ClassVar[int]
    TIME_FIELD_NUMBER: _ClassVar[int]
    id: str
    label: str
    message: str
    satisfied: bool
    time: float
    def __init__(self, id: _Optional[str] = ..., label: _Optional[str] = ..., message: _Optional[str] = ..., satisfied: bool = ..., time: _Optional[float] = ...) -> None: ...

class PbTaskProxy(_message.Message):
    __slots__ = ("stamp", "id", "task", "state", "cycle_point", "depth", "job_submits", "outputs", "namespace", "prerequisites", "jobs", "first_parent", "name", "is_held", "edges", "ancestors", "flow_nums", "external_triggers", "xtriggers", "is_queued", "is_runahead", "flow_wait", "runtime", "graph_depth", "is_retry", "is_wallclock", "is_xtriggered")
    class OutputsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: PbOutput
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[PbOutput, _Mapping]] = ...) -> None: ...
    class ExternalTriggersEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: PbTrigger
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[PbTrigger, _Mapping]] = ...) -> None: ...
    class XtriggersEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: PbTrigger
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[PbTrigger, _Mapping]] = ...) -> None: ...
    STAMP_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    TASK_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    CYCLE_POINT_FIELD_NUMBER: _ClassVar[int]
    DEPTH_FIELD_NUMBER: _ClassVar[int]
    JOB_SUBMITS_FIELD_NUMBER: _ClassVar[int]
    OUTPUTS_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    PREREQUISITES_FIELD_NUMBER: _ClassVar[int]
    JOBS_FIELD_NUMBER: _ClassVar[int]
    FIRST_PARENT_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    IS_HELD_FIELD_NUMBER: _ClassVar[int]
    EDGES_FIELD_NUMBER: _ClassVar[int]
    ANCESTORS_FIELD_NUMBER: _ClassVar[int]
    FLOW_NUMS_FIELD_NUMBER: _ClassVar[int]
    EXTERNAL_TRIGGERS_FIELD_NUMBER: _ClassVar[int]
    XTRIGGERS_FIELD_NUMBER: _ClassVar[int]
    IS_QUEUED_FIELD_NUMBER: _ClassVar[int]
    IS_RUNAHEAD_FIELD_NUMBER: _ClassVar[int]
    FLOW_WAIT_FIELD_NUMBER: _ClassVar[int]
    RUNTIME_FIELD_NUMBER: _ClassVar[int]
    GRAPH_DEPTH_FIELD_NUMBER: _ClassVar[int]
    IS_RETRY_FIELD_NUMBER: _ClassVar[int]
    IS_WALLCLOCK_FIELD_NUMBER: _ClassVar[int]
    IS_XTRIGGERED_FIELD_NUMBER: _ClassVar[int]
    stamp: str
    id: str
    task: str
    state: str
    cycle_point: str
    depth: int
    job_submits: int
    outputs: _containers.MessageMap[str, PbOutput]
    namespace: _containers.RepeatedScalarFieldContainer[str]
    prerequisites: _containers.RepeatedCompositeFieldContainer[PbPrerequisite]
    jobs: _containers.RepeatedScalarFieldContainer[str]
    first_parent: str
    name: str
    is_held: bool
    edges: _containers.RepeatedScalarFieldContainer[str]
    ancestors: _containers.RepeatedScalarFieldContainer[str]
    flow_nums: str
    external_triggers: _containers.MessageMap[str, PbTrigger]
    xtriggers: _containers.MessageMap[str, PbTrigger]
    is_queued: bool
    is_runahead: bool
    flow_wait: bool
    runtime: PbRuntime
    graph_depth: int
    is_retry: bool
    is_wallclock: bool
    is_xtriggered: bool
    def __init__(self, stamp: _Optional[str] = ..., id: _Optional[str] = ..., task: _Optional[str] = ..., state: _Optional[str] = ..., cycle_point: _Optional[str] = ..., depth: _Optional[int] = ..., job_submits: _Optional[int] = ..., outputs: _Optional[_Mapping[str, PbOutput]] = ..., namespace: _Optional[_Iterable[str]] = ..., prerequisites: _Optional[_Iterable[_Union[PbPrerequisite, _Mapping]]] = ..., jobs: _Optional[_Iterable[str]] = ..., first_parent: _Optional[str] = ..., name: _Optional[str] = ..., is_held: bool = ..., edges: _Optional[_Iterable[str]] = ..., ancestors: _Optional[_Iterable[str]] = ..., flow_nums: _Optional[str] = ..., external_triggers: _Optional[_Mapping[str, PbTrigger]] = ..., xtriggers: _Optional[_Mapping[str, PbTrigger]] = ..., is_queued: bool = ..., is_runahead: bool = ..., flow_wait: bool = ..., runtime: _Optional[_Union[PbRuntime, _Mapping]] = ..., graph_depth: _Optional[int] = ..., is_retry: bool = ..., is_wallclock: bool = ..., is_xtriggered: bool = ...) -> None: ...

class PbFamily(_message.Message):
    __slots__ = ("stamp", "id", "name", "meta", "depth", "proxies", "parents", "child_tasks", "child_families", "first_parent", "runtime")
    STAMP_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    META_FIELD_NUMBER: _ClassVar[int]
    DEPTH_FIELD_NUMBER: _ClassVar[int]
    PROXIES_FIELD_NUMBER: _ClassVar[int]
    PARENTS_FIELD_NUMBER: _ClassVar[int]
    CHILD_TASKS_FIELD_NUMBER: _ClassVar[int]
    CHILD_FAMILIES_FIELD_NUMBER: _ClassVar[int]
    FIRST_PARENT_FIELD_NUMBER: _ClassVar[int]
    RUNTIME_FIELD_NUMBER: _ClassVar[int]
    stamp: str
    id: str
    name: str
    meta: PbMeta
    depth: int
    proxies: _containers.RepeatedScalarFieldContainer[str]
    parents: _containers.RepeatedScalarFieldContainer[str]
    child_tasks: _containers.RepeatedScalarFieldContainer[str]
    child_families: _containers.RepeatedScalarFieldContainer[str]
    first_parent: str
    runtime: PbRuntime
    def __init__(self, stamp: _Optional[str] = ..., id: _Optional[str] = ..., name: _Optional[str] = ..., meta: _Optional[_Union[PbMeta, _Mapping]] = ..., depth: _Optional[int] = ..., proxies: _Optional[_Iterable[str]] = ..., parents: _Optional[_Iterable[str]] = ..., child_tasks: _Optional[_Iterable[str]] = ..., child_families: _Optional[_Iterable[str]] = ..., first_parent: _Optional[str] = ..., runtime: _Optional[_Union[PbRuntime, _Mapping]] = ...) -> None: ...

class PbFamilyProxy(_message.Message):
    __slots__ = ("stamp", "id", "cycle_point", "name", "family", "state", "depth", "first_parent", "child_tasks", "child_families", "is_held", "ancestors", "states", "state_totals", "is_held_total", "is_queued", "is_queued_total", "is_runahead", "is_runahead_total", "runtime", "graph_depth", "is_retry", "is_wallclock", "is_xtriggered")
    class StateTotalsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: int
        def __init__(self, key: _Optional[str] = ..., value: _Optional[int] = ...) -> None: ...
    STAMP_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    CYCLE_POINT_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    FAMILY_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    DEPTH_FIELD_NUMBER: _ClassVar[int]
    FIRST_PARENT_FIELD_NUMBER: _ClassVar[int]
    CHILD_TASKS_FIELD_NUMBER: _ClassVar[int]
    CHILD_FAMILIES_FIELD_NUMBER: _ClassVar[int]
    IS_HELD_FIELD_NUMBER: _ClassVar[int]
    ANCESTORS_FIELD_NUMBER: _ClassVar[int]
    STATES_FIELD_NUMBER: _ClassVar[int]
    STATE_TOTALS_FIELD_NUMBER: _ClassVar[int]
    IS_HELD_TOTAL_FIELD_NUMBER: _ClassVar[int]
    IS_QUEUED_FIELD_NUMBER: _ClassVar[int]
    IS_QUEUED_TOTAL_FIELD_NUMBER: _ClassVar[int]
    IS_RUNAHEAD_FIELD_NUMBER: _ClassVar[int]
    IS_RUNAHEAD_TOTAL_FIELD_NUMBER: _ClassVar[int]
    RUNTIME_FIELD_NUMBER: _ClassVar[int]
    GRAPH_DEPTH_FIELD_NUMBER: _ClassVar[int]
    IS_RETRY_FIELD_NUMBER: _ClassVar[int]
    IS_WALLCLOCK_FIELD_NUMBER: _ClassVar[int]
    IS_XTRIGGERED_FIELD_NUMBER: _ClassVar[int]
    stamp: str
    id: str
    cycle_point: str
    name: str
    family: str
    state: str
    depth: int
    first_parent: str
    child_tasks: _containers.RepeatedScalarFieldContainer[str]
    child_families: _containers.RepeatedScalarFieldContainer[str]
    is_held: bool
    ancestors: _containers.RepeatedScalarFieldContainer[str]
    states: _containers.RepeatedScalarFieldContainer[str]
    state_totals: _containers.ScalarMap[str, int]
    is_held_total: int
    is_queued: bool
    is_queued_total: int
    is_runahead: bool
    is_runahead_total: int
    runtime: PbRuntime
    graph_depth: int
    is_retry: bool
    is_wallclock: bool
    is_xtriggered: bool
    def __init__(self, stamp: _Optional[str] = ..., id: _Optional[str] = ..., cycle_point: _Optional[str] = ..., name: _Optional[str] = ..., family: _Optional[str] = ..., state: _Optional[str] = ..., depth: _Optional[int] = ..., first_parent: _Optional[str] = ..., child_tasks: _Optional[_Iterable[str]] = ..., child_families: _Optional[_Iterable[str]] = ..., is_held: bool = ..., ancestors: _Optional[_Iterable[str]] = ..., states: _Optional[_Iterable[str]] = ..., state_totals: _Optional[_Mapping[str, int]] = ..., is_held_total: _Optional[int] = ..., is_queued: bool = ..., is_queued_total: _Optional[int] = ..., is_runahead: bool = ..., is_runahead_total: _Optional[int] = ..., runtime: _Optional[_Union[PbRuntime, _Mapping]] = ..., graph_depth: _Optional[int] = ..., is_retry: bool = ..., is_wallclock: bool = ..., is_xtriggered: bool = ...) -> None: ...

class PbEdge(_message.Message):
    __slots__ = ("stamp", "id", "source", "target", "suicide", "cond")
    STAMP_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    TARGET_FIELD_NUMBER: _ClassVar[int]
    SUICIDE_FIELD_NUMBER: _ClassVar[int]
    COND_FIELD_NUMBER: _ClassVar[int]
    stamp: str
    id: str
    source: str
    target: str
    suicide: bool
    cond: bool
    def __init__(self, stamp: _Optional[str] = ..., id: _Optional[str] = ..., source: _Optional[str] = ..., target: _Optional[str] = ..., suicide: bool = ..., cond: bool = ...) -> None: ...

class PbEdges(_message.Message):
    __slots__ = ("id", "edges", "workflow_polling_tasks", "leaves", "feet")
    ID_FIELD_NUMBER: _ClassVar[int]
    EDGES_FIELD_NUMBER: _ClassVar[int]
    WORKFLOW_POLLING_TASKS_FIELD_NUMBER: _ClassVar[int]
    LEAVES_FIELD_NUMBER: _ClassVar[int]
    FEET_FIELD_NUMBER: _ClassVar[int]
    id: str
    edges: _containers.RepeatedScalarFieldContainer[str]
    workflow_polling_tasks: _containers.RepeatedCompositeFieldContainer[PbPollTask]
    leaves: _containers.RepeatedScalarFieldContainer[str]
    feet: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, id: _Optional[str] = ..., edges: _Optional[_Iterable[str]] = ..., workflow_polling_tasks: _Optional[_Iterable[_Union[PbPollTask, _Mapping]]] = ..., leaves: _Optional[_Iterable[str]] = ..., feet: _Optional[_Iterable[str]] = ...) -> None: ...

class PbEntireWorkflow(_message.Message):
    __slots__ = ("workflow", "tasks", "task_proxies", "jobs", "families", "family_proxies", "edges")
    WORKFLOW_FIELD_NUMBER: _ClassVar[int]
    TASKS_FIELD_NUMBER: _ClassVar[int]
    TASK_PROXIES_FIELD_NUMBER: _ClassVar[int]
    JOBS_FIELD_NUMBER: _ClassVar[int]
    FAMILIES_FIELD_NUMBER: _ClassVar[int]
    FAMILY_PROXIES_FIELD_NUMBER: _ClassVar[int]
    EDGES_FIELD_NUMBER: _ClassVar[int]
    workflow: PbWorkflow
    tasks: _containers.RepeatedCompositeFieldContainer[PbTask]
    task_proxies: _containers.RepeatedCompositeFieldContainer[PbTaskProxy]
    jobs: _containers.RepeatedCompositeFieldContainer[PbJob]
    families: _containers.RepeatedCompositeFieldContainer[PbFamily]
    family_proxies: _containers.RepeatedCompositeFieldContainer[PbFamilyProxy]
    edges: _containers.RepeatedCompositeFieldContainer[PbEdge]
    def __init__(self, workflow: _Optional[_Union[PbWorkflow, _Mapping]] = ..., tasks: _Optional[_Iterable[_Union[PbTask, _Mapping]]] = ..., task_proxies: _Optional[_Iterable[_Union[PbTaskProxy, _Mapping]]] = ..., jobs: _Optional[_Iterable[_Union[PbJob, _Mapping]]] = ..., families: _Optional[_Iterable[_Union[PbFamily, _Mapping]]] = ..., family_proxies: _Optional[_Iterable[_Union[PbFamilyProxy, _Mapping]]] = ..., edges: _Optional[_Iterable[_Union[PbEdge, _Mapping]]] = ...) -> None: ...

class EDeltas(_message.Message):
    __slots__ = ("time", "checksum", "added", "updated", "pruned", "reloaded")
    TIME_FIELD_NUMBER: _ClassVar[int]
    CHECKSUM_FIELD_NUMBER: _ClassVar[int]
    ADDED_FIELD_NUMBER: _ClassVar[int]
    UPDATED_FIELD_NUMBER: _ClassVar[int]
    PRUNED_FIELD_NUMBER: _ClassVar[int]
    RELOADED_FIELD_NUMBER: _ClassVar[int]
    time: float
    checksum: int
    added: _containers.RepeatedCompositeFieldContainer[PbEdge]
    updated: _containers.RepeatedCompositeFieldContainer[PbEdge]
    pruned: _containers.RepeatedScalarFieldContainer[str]
    reloaded: bool
    def __init__(self, time: _Optional[float] = ..., checksum: _Optional[int] = ..., added: _Optional[_Iterable[_Union[PbEdge, _Mapping]]] = ..., updated: _Optional[_Iterable[_Union[PbEdge, _Mapping]]] = ..., pruned: _Optional[_Iterable[str]] = ..., reloaded: bool = ...) -> None: ...

class FDeltas(_message.Message):
    __slots__ = ("time", "checksum", "added", "updated", "pruned", "reloaded")
    TIME_FIELD_NUMBER: _ClassVar[int]
    CHECKSUM_FIELD_NUMBER: _ClassVar[int]
    ADDED_FIELD_NUMBER: _ClassVar[int]
    UPDATED_FIELD_NUMBER: _ClassVar[int]
    PRUNED_FIELD_NUMBER: _ClassVar[int]
    RELOADED_FIELD_NUMBER: _ClassVar[int]
    time: float
    checksum: int
    added: _containers.RepeatedCompositeFieldContainer[PbFamily]
    updated: _containers.RepeatedCompositeFieldContainer[PbFamily]
    pruned: _containers.RepeatedScalarFieldContainer[str]
    reloaded: bool
    def __init__(self, time: _Optional[float] = ..., checksum: _Optional[int] = ..., added: _Optional[_Iterable[_Union[PbFamily, _Mapping]]] = ..., updated: _Optional[_Iterable[_Union[PbFamily, _Mapping]]] = ..., pruned: _Optional[_Iterable[str]] = ..., reloaded: bool = ...) -> None: ...

class FPDeltas(_message.Message):
    __slots__ = ("time", "checksum", "added", "updated", "pruned", "reloaded")
    TIME_FIELD_NUMBER: _ClassVar[int]
    CHECKSUM_FIELD_NUMBER: _ClassVar[int]
    ADDED_FIELD_NUMBER: _ClassVar[int]
    UPDATED_FIELD_NUMBER: _ClassVar[int]
    PRUNED_FIELD_NUMBER: _ClassVar[int]
    RELOADED_FIELD_NUMBER: _ClassVar[int]
    time: float
    checksum: int
    added: _containers.RepeatedCompositeFieldContainer[PbFamilyProxy]
    updated: _containers.RepeatedCompositeFieldContainer[PbFamilyProxy]
    pruned: _containers.RepeatedScalarFieldContainer[str]
    reloaded: bool
    def __init__(self, time: _Optional[float] = ..., checksum: _Optional[int] = ..., added: _Optional[_Iterable[_Union[PbFamilyProxy, _Mapping]]] = ..., updated: _Optional[_Iterable[_Union[PbFamilyProxy, _Mapping]]] = ..., pruned: _Optional[_Iterable[str]] = ..., reloaded: bool = ...) -> None: ...

class JDeltas(_message.Message):
    __slots__ = ("time", "checksum", "added", "updated", "pruned", "reloaded")
    TIME_FIELD_NUMBER: _ClassVar[int]
    CHECKSUM_FIELD_NUMBER: _ClassVar[int]
    ADDED_FIELD_NUMBER: _ClassVar[int]
    UPDATED_FIELD_NUMBER: _ClassVar[int]
    PRUNED_FIELD_NUMBER: _ClassVar[int]
    RELOADED_FIELD_NUMBER: _ClassVar[int]
    time: float
    checksum: int
    added: _containers.RepeatedCompositeFieldContainer[PbJob]
    updated: _containers.RepeatedCompositeFieldContainer[PbJob]
    pruned: _containers.RepeatedScalarFieldContainer[str]
    reloaded: bool
    def __init__(self, time: _Optional[float] = ..., checksum: _Optional[int] = ..., added: _Optional[_Iterable[_Union[PbJob, _Mapping]]] = ..., updated: _Optional[_Iterable[_Union[PbJob, _Mapping]]] = ..., pruned: _Optional[_Iterable[str]] = ..., reloaded: bool = ...) -> None: ...

class TDeltas(_message.Message):
    __slots__ = ("time", "checksum", "added", "updated", "pruned", "reloaded")
    TIME_FIELD_NUMBER: _ClassVar[int]
    CHECKSUM_FIELD_NUMBER: _ClassVar[int]
    ADDED_FIELD_NUMBER: _ClassVar[int]
    UPDATED_FIELD_NUMBER: _ClassVar[int]
    PRUNED_FIELD_NUMBER: _ClassVar[int]
    RELOADED_FIELD_NUMBER: _ClassVar[int]
    time: float
    checksum: int
    added: _containers.RepeatedCompositeFieldContainer[PbTask]
    updated: _containers.RepeatedCompositeFieldContainer[PbTask]
    pruned: _containers.RepeatedScalarFieldContainer[str]
    reloaded: bool
    def __init__(self, time: _Optional[float] = ..., checksum: _Optional[int] = ..., added: _Optional[_Iterable[_Union[PbTask, _Mapping]]] = ..., updated: _Optional[_Iterable[_Union[PbTask, _Mapping]]] = ..., pruned: _Optional[_Iterable[str]] = ..., reloaded: bool = ...) -> None: ...

class TPDeltas(_message.Message):
    __slots__ = ("time", "checksum", "added", "updated", "pruned", "reloaded")
    TIME_FIELD_NUMBER: _ClassVar[int]
    CHECKSUM_FIELD_NUMBER: _ClassVar[int]
    ADDED_FIELD_NUMBER: _ClassVar[int]
    UPDATED_FIELD_NUMBER: _ClassVar[int]
    PRUNED_FIELD_NUMBER: _ClassVar[int]
    RELOADED_FIELD_NUMBER: _ClassVar[int]
    time: float
    checksum: int
    added: _containers.RepeatedCompositeFieldContainer[PbTaskProxy]
    updated: _containers.RepeatedCompositeFieldContainer[PbTaskProxy]
    pruned: _containers.RepeatedScalarFieldContainer[str]
    reloaded: bool
    def __init__(self, time: _Optional[float] = ..., checksum: _Optional[int] = ..., added: _Optional[_Iterable[_Union[PbTaskProxy, _Mapping]]] = ..., updated: _Optional[_Iterable[_Union[PbTaskProxy, _Mapping]]] = ..., pruned: _Optional[_Iterable[str]] = ..., reloaded: bool = ...) -> None: ...

class WDeltas(_message.Message):
    __slots__ = ("time", "added", "updated", "reloaded", "pruned")
    TIME_FIELD_NUMBER: _ClassVar[int]
    ADDED_FIELD_NUMBER: _ClassVar[int]
    UPDATED_FIELD_NUMBER: _ClassVar[int]
    RELOADED_FIELD_NUMBER: _ClassVar[int]
    PRUNED_FIELD_NUMBER: _ClassVar[int]
    time: float
    added: PbWorkflow
    updated: PbWorkflow
    reloaded: bool
    pruned: str
    def __init__(self, time: _Optional[float] = ..., added: _Optional[_Union[PbWorkflow, _Mapping]] = ..., updated: _Optional[_Union[PbWorkflow, _Mapping]] = ..., reloaded: bool = ..., pruned: _Optional[str] = ...) -> None: ...

class AllDeltas(_message.Message):
    __slots__ = ("families", "family_proxies", "jobs", "tasks", "task_proxies", "edges", "workflow")
    FAMILIES_FIELD_NUMBER: _ClassVar[int]
    FAMILY_PROXIES_FIELD_NUMBER: _ClassVar[int]
    JOBS_FIELD_NUMBER: _ClassVar[int]
    TASKS_FIELD_NUMBER: _ClassVar[int]
    TASK_PROXIES_FIELD_NUMBER: _ClassVar[int]
    EDGES_FIELD_NUMBER: _ClassVar[int]
    WORKFLOW_FIELD_NUMBER: _ClassVar[int]
    families: FDeltas
    family_proxies: FPDeltas
    jobs: JDeltas
    tasks: TDeltas
    task_proxies: TPDeltas
    edges: EDeltas
    workflow: WDeltas
    def __init__(self, families: _Optional[_Union[FDeltas, _Mapping]] = ..., family_proxies: _Optional[_Union[FPDeltas, _Mapping]] = ..., jobs: _Optional[_Union[JDeltas, _Mapping]] = ..., tasks: _Optional[_Union[TDeltas, _Mapping]] = ..., task_proxies: _Optional[_Union[TPDeltas, _Mapping]] = ..., edges: _Optional[_Union[EDeltas, _Mapping]] = ..., workflow: _Optional[_Union[WDeltas, _Mapping]] = ...) -> None: ...
