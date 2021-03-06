import re
import os
import sys
import json
import posixpath
from urlparse import urljoin
from docutils import nodes
from docutils.io import StringOutput
from docutils.nodes import document, section

from sphinx import addnodes
from sphinx.environment import url_re
from sphinx.domains import Domain
from sphinx.util.osutil import relative_uri
from sphinx.builders.html import StandaloneHTMLBuilder, DirectoryHTMLBuilder


_edition_re = re.compile(r'^(\s*)..\s+sentry:edition::\s*(.*?)$')
_docedition_re = re.compile(r'^..\s+sentry:docedition::\s*(.*?)$')


EXTERNAL_DOCS_URL = 'https://docs.getsentry.com/hosted/'


def resolve_toctree(env, docname, builder, toctree, collapse=False):
    def _toctree_add_classes(node):
        for subnode in node.children:
            if isinstance(subnode, (addnodes.compact_paragraph,
                                    nodes.list_item,
                                    nodes.bullet_list)):
                _toctree_add_classes(subnode)
            elif isinstance(subnode, nodes.reference):
                # for <a>, identify which entries point to the current
                # document and therefore may not be collapsed
                if subnode['refuri'] == docname:
                    list_item = subnode.parent.parent
                    if not subnode['anchorname']:

                        # give the whole branch a 'current' class
                        # (useful for styling it differently)
                        branchnode = subnode
                        while branchnode:
                            branchnode['classes'].append('current')
                            branchnode = branchnode.parent
                    # mark the list_item as "on current page"
                    if subnode.parent.parent.get('iscurrent'):
                        # but only if it's not already done
                        return
                    while subnode:
                        subnode['iscurrent'] = True
                        subnode = subnode.parent

                    # Now mark all siblings as well and also give the
                    # innermost expansion an extra class.
                    list_item['classes'].append('active')
                    for node in list_item.parent.children:
                        node['classes'].append('relevant')

    def _entries_from_toctree(toctreenode, parents, subtree=False):
        refs = [(e[0], e[1]) for e in toctreenode['entries']]
        entries = []
        for (title, ref) in refs:
            refdoc = None
            if url_re.match(ref):
                raise NotImplementedError('Not going to implement this (url)')
            elif ref == 'env':
                raise NotImplementedError('Not going to implement this (env)')
            else:
                if ref in parents:
                    env.warn(ref, 'circular toctree references '
                             'detected, ignoring: %s <- %s' %
                             (ref, ' <- '.join(parents)))
                    continue
                refdoc = ref
                toc = env.tocs[ref].deepcopy()
                env.process_only_nodes(toc, builder, ref)
                if title and toc.children and len(toc.children) == 1:
                    child = toc.children[0]
                    for refnode in child.traverse(nodes.reference):
                        if refnode['refuri'] == ref and \
                           not refnode['anchorname']:
                            refnode.children = [nodes.Text(title)]
            if not toc.children:
                # empty toc means: no titles will show up in the toctree
                env.warn_node(
                    'toctree contains reference to document %r that '
                    'doesn\'t have a title: no link will be generated'
                    % ref, toctreenode)

            # delete everything but the toplevel title(s)
            # and toctrees
            for toplevel in toc:
                # nodes with length 1 don't have any children anyway
                if len(toplevel) > 1:
                    subtrees = toplevel.traverse(addnodes.toctree)
                    toplevel[1][:] = subtrees

            # resolve all sub-toctrees
            for subtocnode in toc.traverse(addnodes.toctree):
                i = subtocnode.parent.index(subtocnode) + 1
                for item in _entries_from_toctree(subtocnode, [refdoc] +
                                                  parents, subtree=True):
                    subtocnode.parent.insert(i, item)
                    i += 1
                subtocnode.parent.remove(subtocnode)

            entries.extend(toc.children)
        if not subtree:
            ret = nodes.bullet_list()
            ret += entries
            return [ret]
        return entries

    tocentries = _entries_from_toctree(toctree, [])
    if not tocentries:
        return None

    newnode = addnodes.compact_paragraph('', '')
    newnode.extend(tocentries)
    newnode['toctree'] = True

    _toctree_add_classes(newnode)

    for refnode in newnode.traverse(nodes.reference):
        if not url_re.match(refnode['refuri']):
            refnode.parent.parent['classes'].append('ref-' + refnode['refuri'])
            refnode['refuri'] = builder.get_relative_uri(
                docname, refnode['refuri']) + refnode['anchorname']

    return newnode


def make_link_builder(app, base_page):
    def link_builder(edition, to_current=False):
        here = app.builder.get_target_uri(base_page)
        if to_current:
            uri = relative_uri(here, '../' + edition + '/' +
                               here.lstrip('/')) or './'
        else:
            root = app.builder.get_target_uri(app.env.config.master_doc) or './'
            uri = relative_uri(here, root) or ''
            if app.builder.name in ('sentryhtml', 'html'):
                uri = (posixpath.dirname(uri or '.') or '.').rstrip('/') + \
                    '/../' + edition + '/index.html'
            else:
                uri = uri.rstrip('/') + '/../' + edition + '/'
        return uri
    return link_builder


def html_page_context(app, pagename, templatename, context, doctree):
    # toc_parts = get_rendered_toctree(app.builder, pagename)
    # context['full_toc'] = toc_parts['main']

    def build_toc(split_toc=None):
        return get_rendered_toctree(app.builder, pagename, collapse=False,
                                    split_toc=split_toc)
    context['build_toc'] = build_toc

    context['link_to_edition'] = make_link_builder(app, pagename)

    def render_sitemap():
        return get_rendered_toctree(app.builder, 'sitemap',
                                    collapse=False)['main']
    context['render_sitemap'] = render_sitemap

    context['sentry_doc_variant'] = app.env.config.sentry_doc_variant


def extract_toc(fulltoc, selectors):
    entries = []

    for refnode in fulltoc.traverse(nodes.reference):
        container = refnode.parent.parent
        if any(cls[:4] == 'ref-' and cls[4:] in selectors
               for cls in container['classes']):
            parent = container.parent

            new_parent = parent.deepcopy()
            del new_parent.children[:]
            new_parent += container
            entries.append(new_parent)

            parent.remove(container)
            if not parent.children:
                parent.parent.remove(parent)

    newnode = addnodes.compact_paragraph('', '')
    newnode.extend(entries)
    newnode['toctree'] = True

    return newnode


def get_rendered_toctree(builder, docname, collapse=True, split_toc=None):
    fulltoc = build_full_toctree(builder, docname, collapse=collapse)

    rv = {}

    def _render_toc(node):
        return builder.render_partial(node)['fragment']

    if split_toc:
        for key, selectors in split_toc.iteritems():
            rv[key] = _render_toc(extract_toc(fulltoc, selectors))

    rv['main'] = _render_toc(fulltoc)
    return rv


def build_full_toctree(builder, docname, collapse=True):
    env = builder.env
    doctree = env.get_doctree(env.config.master_doc)
    toctrees = []
    for toctreenode in doctree.traverse(addnodes.toctree):
        toctrees.append(resolve_toctree(env, docname, builder, toctreenode,
                                        collapse=collapse))
    if not toctrees:
        return None
    result = toctrees[0]
    for toctree in toctrees[1:]:
        if toctree:
            result.extend(toctree.children)
    env.resolve_references(result, docname, builder)
    return result


def parse_rst(state, content_offset, doc):
    node = nodes.section()
    # hack around title style bookkeeping
    surrounding_title_styles = state.memo.title_styles
    surrounding_section_level = state.memo.section_level
    state.memo.title_styles = []
    state.memo.section_level = 0
    state.nested_parse(doc, content_offset, node, match_titles=1)
    state.memo.title_styles = surrounding_title_styles
    state.memo.section_level = surrounding_section_level
    return node.children


class SentryDomain(Domain):
    name = 'sentry'
    label = 'Sentry'
    directives = {
    }


def preprocess_source(app, docname, source):
    source_lines = source[0].splitlines()

    def _find_block(indent, lineno):
        block_indent = len(indent.expandtabs())
        rv = []
        actual_indent = None

        while lineno < end:
            line = source_lines[lineno]
            if not line.strip():
                rv.append(u'')
            else:
                expanded_line = line.expandtabs()
                indent = len(expanded_line) - len(expanded_line.lstrip())
                if indent > block_indent:
                    if actual_indent is None or indent < actual_indent:
                        actual_indent = indent
                    rv.append(line)
                else:
                    break
            lineno += 1

        if rv:
            rv.append(u'')
            if actual_indent:
                rv = [x[actual_indent:] for x in rv]
        return rv, lineno

    result = []

    lineno = 0
    end = len(source_lines)
    while lineno < end:
        line = source_lines[lineno]
        match = _edition_re.match(line)
        if match is None:
            # Skip sentry:docedition.  We don't want those.
            match = _docedition_re.match(line)
            if match is None:
                result.append(line)
            lineno += 1
            continue
        lineno += 1
        indent, tags = match.groups()
        tags = set(x.strip() for x in tags.split(',') if x.strip())
        should_include = app.env.config.sentry_doc_variant in tags
        block_lines, lineno = _find_block(indent, lineno)
        if should_include:
            result.extend(block_lines)

    source[:] = [u'\n'.join(result)]


def builder_inited(app):
    # XXX: this currently means thigns only stay referenced after a
    # deletion of a link after a clean build :(
    if not hasattr(app.env, 'sentry_referenced_docs'):
        app.env.sentry_referenced_docs = {}


def track_references(app, doctree):
    docname = app.env.temp_data['docname']
    rd = app.env.sentry_referenced_docs
    for toctreenode in doctree.traverse(addnodes.toctree):
        for e in toctreenode['entries']:
            rd.setdefault(str(e[1]), set()).add(docname)


def is_referenced(docname, references):
    if docname == 'index':
        return True
    seen = set([docname])
    to_process = set(references.get(docname) or ())
    while to_process:
        if 'index' in to_process:
            return True
        next = to_process.pop()
        seen.add(next)
        for backlink in references.get(next) or ():
            if backlink in seen:
                continue
            else:
                to_process.add(backlink)
    return False


class SphinxBuilderMixin(object):
    build_wizard_fragment = False

    @property
    def add_permalinks(self):
        return not self.build_wizard_fragment

    def get_target_uri(self, *args, **kwargs):
        rv = super(SphinxBuilderMixin, self).get_target_uri(*args, **kwargs)
        if self.build_wizard_fragment:
            rv = urljoin(EXTERNAL_DOCS_URL, rv)
        return rv

    def get_relative_uri(self, from_, to, typ=None):
        if self.build_wizard_fragment:
            return self.get_target_uri(to, typ)
        return super(SphinxBuilderMixin, self).get_relative_uri(
            from_, to, typ)

    def write_doc(self, docname, doctree):
        if is_referenced(docname, self.app.env.sentry_referenced_docs):
            return super(SphinxBuilderMixin, self).write_doc(docname, doctree)
        else:
            print 'skipping because unreferenced'

    def __iter_wizard_files(self):
        for dirpath, dirnames, filenames in os.walk(self.srcdir):
            dirnames[:] = [x for x in dirnames if x[:1] not in '_.']
            for filename in filenames:
                if filename == 'sentry-doc-config.json':
                    full_path = os.path.join(self.srcdir, dirpath)
                    base_path = full_path[len(self.srcdir):].strip('/\\') \
                        .replace(os.path.sep, '/')
                    yield os.path.join(full_path, filename), base_path

    def __build_wizard_section(self, base_path, snippets):
        trees = {}
        rv = []

        def _build_node(node):
            original_header_level = self.docsettings.initial_header_level
            # bump initial header level to two
            self.docsettings.initial_header_level = 2
            # indicate that we're building for the wizard fragements.
            # This changes url generation and more.
            self.build_wizard_fragment = True
            # Embed pygments colors as inline styles
            original_args = self.highlighter.formatter_args
            self.highlighter.formatter_args = original_args.copy()
            self.highlighter.formatter_args['noclasses'] = True
            try:
                sub_doc = document(self.docsettings,
                                   doctree.reporter)
                sub_doc += node
                destination = StringOutput(encoding='utf-8')
                self.current_docname = docname
                self.docwriter.write(sub_doc, destination)
                self.docwriter.assemble_parts()
                rv.append(self.docwriter.parts['fragment'])
            finally:
                self.build_wizard_fragment = False
                self.highlighter.formatter_args = original_args
                self.docsettings.initial_header_level = original_header_level

        for snippet in snippets:
            if '#' not in snippet:
                snippet_path = snippet
                section_name = None
            else:
                snippet_path, section_name = snippet.split('#', 1)
            docname = posixpath.join(base_path, snippet_path)
            if docname in trees:
                doctree = trees.get(docname)
            else:
                doctree = self.env.get_and_resolve_doctree(docname, self)
                trees[docname] = doctree

            if section_name is None:
                _build_node(next(iter(doctree.traverse(section))))
            else:
                for sect in doctree.traverse(section):
                    if section_name in sect['ids']:
                        _build_node(sect)

        return u'\n\n'.join(rv)

    def __write_wizard(self, data, base_path):
        for uid, framework_data in data.get('wizards', {}).iteritems():
            body = self.__build_wizard_section(base_path,
                                               framework_data['snippets'])

            fn = os.path.join(self.outdir, '_wizards', '%s.json' % uid)
            try:
                os.makedirs(os.path.dirname(fn))
            except OSError:
                pass

            doc_link = framework_data.get('doc_link')
            if doc_link is not None:
                doc_link = urljoin(EXTERNAL_DOCS_URL,
                                   posixpath.join(base_path, doc_link))
            with open(fn, 'w') as f:
                json.dump({
                    'name': framework_data.get('name') or uid.title(),
                    'is_framework': framework_data.get('is_framework', False),
                    'doc_link': doc_link,
                    'client_lib': framework_data.get('client_lib'),
                    'body': body
                }, f)
                f.write('\n')

    def __write_wizards(self):
        for filename, base_path in self.__iter_wizard_files():
            with open(filename) as f:
                data = json.load(f)
                self.__write_wizard(data, base_path)

    def finish(self):
        super(SphinxBuilderMixin, self).finish()
        self.__write_wizards()


class SentryStandaloneHTMLBuilder(SphinxBuilderMixin, StandaloneHTMLBuilder):
    name = 'sentryhtml'


class SentryDirectoryHTMLBuilder(SphinxBuilderMixin, DirectoryHTMLBuilder):
    name = 'sentrydirhtml'


def setup(app):
    from sphinx.highlighting import lexers
    from pygments.lexers.web import PhpLexer
    lexers['php'] = PhpLexer(startinline=True)

    app.add_domain(SentryDomain)
    app.connect('builder-inited', builder_inited)
    app.connect('html-page-context', html_page_context)
    app.connect('source-read', preprocess_source)
    app.connect('doctree-read', track_references)
    app.add_builder(SentryStandaloneHTMLBuilder)
    app.add_builder(SentryDirectoryHTMLBuilder)
    app.add_config_value('sentry_doc_variant', None, 'env')


def activate():
    """Changes the config to something that the sentry doc infrastructure
    expects.
    """
    frm = sys._getframe(1)
    globs = frm.f_globals

    globs.setdefault('sentry_doc_variant',
                     os.environ.get('SENTRY_DOC_VARIANT', 'self'))
    globs['extensions'] = list(globs.get('extensions') or ()) + ['sentryext']
    globs['primary_domain'] = 'std'
    globs['exclude_patterns'] = list(globs.get('exclude_patterns')
                                     or ()) + ['_sentryext']
