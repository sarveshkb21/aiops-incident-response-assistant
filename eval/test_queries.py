"""
eval/test_queries.py - Evaluation query set

20 test queries spanning all specialist domains plus deliberately ambiguous /
off-domain queries that should be classified `general` by the router.

Each case:
  id              - stable identifier
  query           - what the engineer types
  expected_domain - the domain a human would route this to
  expected_source - optional runbook-filename substring the retrieval should
                    surface; when omitted, a retrieval "hit" means at least one
                    retrieved chunk carries the expected domain metadata
                    (for `general`, any retrieved chunk counts).

The three `general` cases are intentionally ambiguous or off-domain: the
correct behaviour is that the ROUTER classifies them `general` directly, so
the unfiltered General agent answers. (The app's separate empty-retrieval
fallback only fires when a routed domain has zero documents — see summary.md.)
"""

QUERIES = [
    # --- kubernetes -------------------------------------------------------
    {
        "id": "k8s-01",
        "query": "Pods keep getting OOMKilled and restarting in production - how do I fix this?",
        "expected_domain": "kubernetes",
        "expected_source": "runbook_oom_kubernetes",
    },
    {
        "id": "k8s-02",
        "query": "How do I find which container in a pod exceeded its memory limit?",
        "expected_domain": "kubernetes",
        "expected_source": "runbook_oom_kubernetes",
    },
    # --- database ---------------------------------------------------------
    {
        "id": "db-01",
        "query": "Database connection pool exhausted - applications cannot get connections. What do I do?",
        "expected_domain": "database",
        "expected_source": "runbook_database",
    },
    {
        "id": "db-02",
        "query": "Replication lag keeps growing on our read replica and queries return stale data.",
        "expected_domain": "database",
        "expected_source": "runbook_database",
    },
    {
        "id": "db-03",
        "query": "Deadlocks are spiking on the orders table in production SQL.",
        "expected_domain": "database",
        "expected_source": "runbook_database",
    },
    # --- infrastructure ----------------------------------------------------
    {
        "id": "infra-01",
        "query": "High CPU alert on a Linux server, load average is 40 - remediation steps?",
        "expected_domain": "infrastructure",
        "expected_source": "runbook_high_cpu",
    },
    {
        "id": "infra-02",
        "query": "Disk space at 95% on the application server and climbing.",
        "expected_domain": "infrastructure",
        "expected_source": "runbook_disk_space",
    },
    {
        "id": "infra-03",
        "query": "The service health check keeps failing intermittently on our API host.",
        "expected_domain": "infrastructure",
        "expected_source": "runbook_service_health",
    },
    # --- network ------------------------------------------------------------
    {
        "id": "net-01",
        "query": "DNS resolution is failing intermittently across several services - how to debug?",
        "expected_domain": "network",
        "expected_source": "runbook_dns_failure",
    },
    {
        "id": "net-02",
        "query": "Users report very high latency to the API and ping times have spiked.",
        "expected_domain": "network",
        "expected_source": "runbook_high_latency",
    },
    {
        "id": "net-03",
        "query": "The load balancer is showing packet loss to its backend targets.",
        "expected_domain": "network",
        "expected_source": None,
    },
    # --- security -----------------------------------------------------------
    {
        "id": "sec-01",
        "query": "Suspicious login from an unknown IP address on a production server - what now?",
        "expected_domain": "security",
        "expected_source": "runbook_unauthorized_access",
    },
    {
        "id": "sec-02",
        "query": "Our TLS certificate expires tomorrow. What is the renewal procedure?",
        "expected_domain": "security",
        "expected_source": "runbook_ssl_cert_expiry",
    },
    {
        "id": "sec-03",
        "query": "We are seeing brute-force SSH attempts against a bastion host.",
        "expected_domain": "security",
        "expected_source": "runbook_unauthorized_access",
    },
    # --- cicd (added by the extensibility test) ------------------------------
    {
        "id": "cicd-01",
        "query": "GitHub Actions pipeline has been stuck in queued for two hours and is blocking a hotfix.",
        "expected_domain": "cicd",
        "expected_source": "runbook_pipeline_stuck",
    },
    {
        "id": "cicd-02",
        "query": "Our release pipeline shipped a bad build to production - how do I roll back the release?",
        "expected_domain": "cicd",
        "expected_source": "runbook_failed_deployment",
    },
    {
        "id": "cicd-03",
        "query": "docker push to the artifact registry fails with 401 unauthorized in CI.",
        "expected_domain": "cicd",
        "expected_source": "runbook_artifact_registry",
    },
    # --- general / deliberately ambiguous ------------------------------------
    {
        "id": "gen-01",
        "query": "Our office printer says PC LOAD LETTER, what now?",
        "expected_domain": "general",
        "expected_source": None,
    },
    {
        "id": "gen-02",
        "query": "What is the general process for handling a SEV-1 incident end to end?",
        "expected_domain": "general",
        "expected_source": None,
    },
    {
        "id": "gen-03",
        "query": "Something is wrong in prod, users are complaining, but I do not know where to start.",
        "expected_domain": "general",
        "expected_source": None,
    },
]
