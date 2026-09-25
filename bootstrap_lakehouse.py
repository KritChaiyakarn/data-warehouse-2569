import os

def create_directory_structure():
    """Generates the local project folders for configs and persistent data storage."""
    dirs = [
        "config/trino",
        "config/superset",
        "volumes/postgres_metadata",
        "volumes/minio_storage",
        "volumes/hive_metastore",
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        print(f"✔ Created directory: {d}")

def write_trino_configs():
    """Writes the required Trino engine configurations and the Iceberg connector."""
    # Main Trino config
    node_properties = """node.environment=production
node.id=ffffffff-ffff-ffff-ffff-ffffffffffff
node.data-dir=/data/trino
"""
    jvm_config = """-server
-Xmx2G
-XX:+UseG1GC
-XX:G1ReservePercent=15
-XX:InitialCodeCacheSize=32m
-XX:ReservedCodeCacheSize=256m
-XX:+UseCodeCacheFlushing
-XX:+AlwaysPreTouch
-XX:+ExplicitGCInvokesConcurrent
"""
    config_properties = """coordinator=true
node-scheduler.include-coordinator=true
http-server.http.port=8080
query.max-memory=1.5GB
query.max-memory-per-node=1GB
query.max-total-memory-per-node=1GB
discovery.uri=http://localhost:8080
"""
    
    # Iceberg catalog configuration pointing to Hive Metastore and MinIO
    iceberg_properties = """connector.name=iceberg
iceberg.catalog.type=hive_metastore
hive.metastore.uri=thrift://hive-metastore:9083
hive.s3.aws-access-key=admin123
hive.s3.aws-secret-key=adminsecret123
hive.s3.endpoint=http://minio:9000
hive.s3.path-style-access=true
hive.s3.ssl.enabled=false
"""

    with open("config/trino/node.properties", "w") as f: f.write(node_properties)
    with open("config/trino/jvm.config", "w") as f: f.write(jvm_config)
    with open("config/trino/config.properties", "w") as f: f.write(config_properties)
    
    os.makedirs("config/trino/catalog", exist_ok=True)
    with open("config/trino/catalog/iceberg.properties", "w") as f: f.write(iceberg_properties)
    print("✔ Generated Trino cluster & Iceberg connector configurations.")

def write_docker_compose():
    """Generates the monolithic docker-compose file orchestrating the infrastructure."""
    compose_content = """version: '3.8'

networks:
  lakehouse-net:
    name: lakehouse-net
    driver: bridge

services:
  # --- METADATA LAYER: Shared Postgres DB for Superset & Hive Metastore State ---
  metadata-db:
    image: postgres:15-alpine
    container_name: metadata-db
    environment:
      POSTGRES_USER: lakehouse_admin
      POSTGRES_PASSWORD: meta_password_123
      POSTGRES_MULTIPLE_DATABASES: superset,metastore
    volumes:
      - ./volumes/postgres_metadata:/var/lib/postgresql/data
      # Entrypoint script to provision both databases on startup
      - ./config/postgres-init.sql:/docker-entrypoint-initdb.d/init.sql
    networks:
      - lakehouse-net
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U lakehouse_admin -d postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  # --- STORAGE LAYER: S3-Compatible Object Store ---
  minio:
    image: minio/minio:RELEASE.2024-01-11T05-49-32Z
    container_name: minio
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: admin123
      MINIO_ROOT_PASSWORD: adminsecret123
    volumes:
      - ./volumes/minio_storage:/data
    networks:
      - lakehouse-net
    command: server /data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 5s
      timeout: 5s
      retries: 5

  # Automatically provision the initial warehouse bucket inside MinIO
  minio-create-bucket:
    image: minio/mc:RELEASE.2024-01-11T06-31-08Z
    container_name: minio-bucket-provisioner
    depends_on:
      minio:
        condition: service_healthy
    networks:
      - lakehouse-net
    entrypoint: >
      /bin/sh -c "
      /usr/bin/mc alias set myminio http://minio:9000 admin123 adminsecret123;
      /usr/bin/mc mb myminio/warehouse || true;
      exit 0;
      "

  # --- CATALOG LAYER: Apache Hive Metastore ---
  hive-metastore:
    image: bitsondatadev/hive-metastore:3.1.2
    container_name: hive-metastore
    depends_on:
      metadata-db:
        condition: service_healthy
    environment:
      DB_DRIVER: postgres
      METASTORE_DB_URL: jdbc:postgresql://metadata-db:5432/metastore
      METASTORE_DB_USER: lakehouse_admin
      METASTORE_DB_PASS: meta_password_123
      AWS_ACCESS_KEY_ID: admin123
      AWS_SECRET_ACCESS_KEY: adminsecret123
      MINIO_ENDPOINT: http://minio:9000
    ports:
      - "9083:9083"
    networks:
      - lakehouse-net

  # --- COMPUTE ENGINE: Trino MPP SQL Engine ---
  trino:
    image: trinodb/trino:438
    container_name: trino
    depends_on:
      minio:
        condition: service_healthy
    ports:
      - "8080:8080"
    volumes:
      - ./config/trino/node.properties:/etc/trino/node.properties
      - ./config/trino/jvm.config:/etc/trino/jvm.config
      - ./config/trino/config.properties:/etc/trino/config.properties
      - ./config/trino/catalog/iceberg.properties:/etc/trino/catalog/iceberg.properties
    networks:
      - lakehouse-net

  # --- BI LAYER: Apache Superset ---
  superset:
    image: apache/superset:3.1.0
    container_name: superset
    ports:
      - "8088:8088"
    depends_on:
      metadata-db:
        condition: service_healthy
    environment:
      SUPERSET_SECRET_KEY: "change_this_to_a_robust_random_string_in_production"
      SQLALCHEMY_DATABASE_URI: "postgresql://lakehouse_admin:meta_password_123@metadata-db:5432/superset"
    volumes:
      - ./config/superset:/app/docker
    networks:
      - lakehouse-net
    # Inits the superset DB app, provisions admin user, and creates default roles
    entrypoint: >
      /bin/sh -c "
      superset db upgrade &&
      superset fab create-admin --username admin --firstname Admin --lastname User --email admin@lakehouse.local --password admin &&
      superset init &&
      /usr/bin/run-server.sh
      "
"""
    with open("docker-compose.yml", "w") as f:
        f.write(compose_content)
    
    # Write SQL helper initialization script for Postgres to provision two schemas
    postgres_init_sql = """CREATE DATABASE superset;
CREATE DATABASE metastore;
GRANT ALL PRIVILEGES ON DATABASE superset TO lakehouse_admin;
GRANT ALL PRIVILEGES ON DATABASE metastore TO lakehouse_admin;
"""
    with open("config/postgres-init.sql", "w") as f:
        f.write(postgres_init_sql)

    print("✔ Generated docker-compose.yml & Postgres initializers.")

if __name__ == "__main__":
    print("🚀 Initializing Open Source Lakehouse Stack Scaffolding...")
    create_directory_structure()
    write_trino_configs()
    write_docker_compose()
    print("\n🎉 Setup Complete! You can now start the environment by running:")
    print("👉 docker compose up -d")

