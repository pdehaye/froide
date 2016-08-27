# -*- encoding: utf-8 -*-
import requests

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.template.defaultfilters import slugify
from django.utils.six import StringIO, BytesIO, PY3

from taggit.utils import parse_tags

if PY3:
    import csv
else:
    import unicodecsv as csv


from froide.publicbody.models import (PublicBody, PublicBodyTag, Jurisdiction, FoiLaw)

User = get_user_model()


class CSVImporter(object):
    topic_cache = {}
    default_topic = None
    jur_cache = {}

    def __init__(self):
        self.user = User.objects.order_by('id')[0]
        self.site = Site.objects.get_current()

    def import_from_url(self, url):
        response = requests.get(url)
        # Force requests to evaluate as UTF-8
        response.encoding = 'utf-8'
        csv_file = BytesIO(response.content)
        self.import_from_file(csv_file)

    def import_from_file(self, csv_file):
        """
        csv_file should be encoded in utf-8
        """
        if PY3:
            csv_file = StringIO(csv_file.read().decode('utf-8'))
        reader = csv.DictReader(csv_file)
        for row in reader:
            self.import_row(row)

    def import_row(self, row):
        # generate slugs
        row['name'] = row['name'].strip()
        row['email'] = row['email'].lower()
        if row['url'] and not row['url'].startswith(('http://', 'https://')):
            row['url'] = 'http://' + row['url']
        row['slug'] = slugify(row['name'])
        row['classification_slug'] = slugify(row['classification'])

        def comma_splitter(tag_string):
            return [t.strip() for t in tag_string.split(',') if t.strip()]

        tags = comma_splitter(row.pop('tags', ''))
        # Backwards compatible handling of topic__slug
        topic_slug = row.pop('topic__slug', None)
        if topic_slug:
            tags.append(self.get_topic(topic_slug))

        # resolve foreign keys
        row['jurisdiction'] = self.get_jurisdiction(row.pop('jurisdiction__slug'))
        parent = row.pop('parent__name', None)
        if parent:
            row['parent'] = PublicBody.objects.get(slug=slugify(parent))

        # get optional values
        for n in ('description', 'other_names', 'request_note', 'website_dump'):
            row[n] = row.get(n, '')

        try:
            if 'id' in row and row['id']:
                pb = PublicBody.objects.get(id=row['id'])
            else:
                pb = PublicBody.objects.get(slug=row['slug'])
            # If it exists, update it
            row.pop('id', None)  # Do not update id though
            row['_updated_by'] = self.user
            PublicBody.objects.filter(id=pb.id).update(**row)
            pb.laws.clear()
            pb.laws.add(*row['jurisdiction'].laws)
            pb.tags.set(*tags)
            return
        except PublicBody.DoesNotExist:
            pass
        row.pop('id', None)  # Remove id if present
        public_body = PublicBody(**row)
        public_body._created_by = self.user
        public_body._updated_by = self.user
        public_body.confirmed = True
        public_body.site = self.site
        public_body.save()
        public_body.laws.add(*row['jurisdiction'].laws)
        public_body.tags.set(*list(tags))

    def get_jurisdiction(self, slug):
        if slug not in self.jur_cache:
            jur = Jurisdiction.objects.get(slug=slug)
            laws = FoiLaw.objects.filter(jurisdiction=jur)
            jur.laws = laws
            self.jur_cache[slug] = jur
        return self.jur_cache[slug]

    def get_topic(self, slug):
        if slug not in self.topic_cache:
            self.topic_cache[slug] = PublicBodyTag.objects.get(slug=slug, is_topic=True)
        return self.topic_cache[slug]
