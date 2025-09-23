from tortoise import fields
from tortoise.models import Model


class Subreddit(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255, unique=True)
    flair: fields.ReverseRelation["Flair"]
    replies: fields.ReverseRelation["Reply"]

    class Meta:
        table = "Subreddit"


class Flair(Model):
    id = fields.IntField(pk=True)
    fid = fields.CharField(max_length=255)
    name = fields.CharField(max_length=255)
    replies = fields.ReverseRelation["Reply"]
    subreddit = fields.ForeignKeyField("models.Subreddit", related_name="flairs", null=True)

    class Meta:
        table = "Flair"


class Reply(Model):
    id = fields.IntField(pk=True)
    text = fields.TextField(null=True)
    submission_id = fields.CharField(max_length=255)
    comment_id = fields.CharField(max_length=255)
    reference_submission_id = fields.CharField(max_length=255)
    reference_comment_id = fields.CharField(max_length=255)
    reference_author = fields.CharField(max_length=255)
    flair = fields.ForeignKeyField("models.Flair", related_name="replies", null=True)
    subreddit = fields.ForeignKeyField("models.Subreddit", related_name="replies", null=True)

    class Meta:
        table = "Reply"
