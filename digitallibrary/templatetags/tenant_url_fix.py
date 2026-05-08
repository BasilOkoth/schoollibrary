from django import template
from django.template.defaulttags import url as builtin_url_tag
from django.urls import reverse, NoReverseMatch

register = template.Library()


class TenantAwareURLNode(template.Node):
    def __init__(self, url_node):
        self.view_name = url_node.view_name
        self.args = url_node.args
        self.kwargs = url_node.kwargs
        self.asvar = url_node.asvar

    def render(self, context):
        args = [arg.resolve(context) for arg in self.args]
        kwargs = {k: v.resolve(context) for k, v in self.kwargs.items()}
        view_name = self.view_name.resolve(context)

        try:
            current_app = context.request.current_app
        except AttributeError:
            current_app = None

        url = ''
        try:
            url = reverse(view_name, args=args, kwargs=kwargs, current_app=current_app)
        except NoReverseMatch:
            try:
                url = reverse(view_name, args=args, kwargs=kwargs, current_app=None)
            except NoReverseMatch:
                if self.asvar:
                    context[self.asvar] = ''
                    return ''
                raise

        if self.asvar:
            context[self.asvar] = url
            return ''
        return url


@register.tag('url')
def url_tag(parser, token):
    node = builtin_url_tag(parser, token)
    return TenantAwareURLNode(node)
