from datetime import date, datetime, timedelta

from django.db import models

import bleach
from constance import config
from django_mysql.models import QuerySet

from .constants import (ALLOWED_TAGS, ALLOWED_ATTRIBUTES, ALLOWED_PROTOCOLS,
                        ALLOWED_STYLES)
from .content import parse as parse_content


class BaseDocumentManager(models.Manager):
    """Manager for Documents, assists for queries"""
    def get_queryset(self):
        return QuerySet(self.model)

    def clean_content(self, content_in):
        tags = ALLOWED_TAGS
        attributes = ALLOWED_ATTRIBUTES
        styles = ALLOWED_STYLES
        protocols = ALLOWED_PROTOCOLS
        allowed_hosts = config.KUMA_WIKI_IFRAME_ALLOWED_HOSTS

        bleached_content = bleach.clean(content_in, attributes=attributes,
                                        tags=tags, styles=styles,
                                        protocols=protocols)
        filtered_content = (parse_content(bleached_content)
                            .filterIframeHosts(allowed_hosts)
                            .serialize())
        return filtered_content

    def get_by_natural_key(self, locale, slug):
        return self.get(locale=locale, slug=slug)

    def get_by_stale_rendering(self):
        """Find documents whose renderings have gone stale"""
        return (self.exclude(render_expires__isnull=True)
                    .filter(render_expires__lte=datetime.now()))

    def filter_for_list(self, locale=None, tag=None, tag_name=None,
                        errors=None, noparent=None, toplevel=None):
        docs = (self.filter(is_redirect=False)
                    .exclude(slug__startswith='User:')
                    .exclude(slug__startswith='Talk:')
                    .exclude(slug__startswith='User_talk:')
                    .exclude(slug__startswith='Template_talk:')
                    .exclude(slug__startswith='Project_talk:')
                    .order_by('slug'))
        if locale:
            docs = docs.filter(locale=locale)
        if tag:
            docs = docs.filter(tags__in=[tag])
        if tag_name:
            docs = docs.filter(tags__name=tag_name)
        if errors:
            docs = (docs.exclude(rendered_errors__isnull=True)
                        .exclude(rendered_errors__exact='[]'))
        if noparent:
            # List translated pages without English source associated
            docs = docs.filter(parent__isnull=True)
        if toplevel:
            docs = docs.filter(parent_topic__isnull=True)

        # Leave out the html, since that leads to huge cache objects and we
        # never use the content in lists.
        docs = docs.defer('html')
        return docs

    def filter_for_review(self, locale=None, tag=None, tag_name=None):
        """Filter for documents with current revision flagged for review"""
        query = 'current_revision__review_tags__%s'
        if tag_name:
            query = {query % 'name': tag_name}
        elif tag:
            query = {query % 'in': [tag]}
        else:
            query = {query % 'name__isnull': False}
        if locale:
            query['locale'] = locale
        return self.filter(**query).distinct()

    def filter_with_localization_tag(self, locale=None, tag=None, tag_name=None):
        """Filter for documents with a localization tag on current revision"""
        query = 'current_revision__localization_tags__%s'
        if tag_name:
            query = {query % 'name': tag_name}
        elif tag:
            query = {query % 'in': [tag]}
        else:
            query = {query % 'name__isnull': False}
        if locale:
            query['locale'] = locale
        return self.filter(**query).distinct()


class DocumentManager(BaseDocumentManager):
    """
    The actual manager, which filters to show only non-deleted pages.
    """
    def get_queryset(self):
        return super(DocumentManager, self).get_queryset().filter(deleted=False)


class DeletedDocumentManager(BaseDocumentManager):
    """
    Specialized manager for working with deleted pages.
    """
    def get_queryset(self):
        return super(DeletedDocumentManager, self).get_queryset().filter(deleted=True)


class DocumentAdminManager(BaseDocumentManager):
    """
    A manager used only in the admin site, which does not perform any
    filtering based on deleted status.
    """


class TaggedDocumentManager(models.Manager):
    def get_queryset(self):
        base_qs = super(TaggedDocumentManager, self).get_queryset()
        return base_qs.filter(content_object__deleted=False)


class RevisionIPManager(models.Manager):

    def delete_old(self, days=30):
        cutoff_date = date.today() - timedelta(days=days)
        old_rev_ips = self.filter(revision__created__lte=cutoff_date)
        old_rev_ips.delete()

    def log(self, revision, headers, data):
        """
        Records the IP and some more data for the given revision and the
        request headers.
        """
        self.create(
            revision=revision,
            ip=headers.get('REMOTE_ADDR'),
            user_agent=headers.get('HTTP_USER_AGENT', ''),
            referrer=headers.get('HTTP_REFERER', ''),
            data=data
        )
