git clone https://github.com/apache/superset
cd superset
#git tags
git checkout tags/6.0.0
docker compose -f docker-compose-image-tag.yml up