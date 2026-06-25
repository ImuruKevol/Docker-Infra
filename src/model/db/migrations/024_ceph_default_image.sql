ALTER TABLE ceph_clusters
    ALTER COLUMN ceph_image SET DEFAULT 'quay.io/ceph/ceph:v19.2.4';

UPDATE ceph_clusters
SET ceph_image = 'quay.io/ceph/ceph:v19.2.4'
WHERE ceph_image IN ('quay.io/ceph/ceph:latest', 'quay.io/ceph/ceph:v19');
