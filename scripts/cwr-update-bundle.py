#!/usr/bin/env python3

from pathlib import Path
import sys
import yaml


bundle_fname = sys.argv[1]
bundle_app_name = sys.argv[2]
charm_build_dir = sys.argv[3]
orig_bundle = Path('/tmp/bundles/%s/bundle.yaml' % bundle_fname)
new_bundle = Path('/tmp/bundles/%s/bundle-cwr.yaml' % bundle_fname)

with orig_bundle.open('r') as fp:
    bundle = yaml.safe_load(fp)
app = bundle.get('applications', bundle.get('services', {}))[bundle_app_name]
app['charm'] = charm_build_dir
with new_bundle.open('w') as fp:
    yaml.dump(bundle, fp)
