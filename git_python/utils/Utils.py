def changes_to_be_committed(repo):
    default_args = ('--abbrev=40', '--full-index', '--raw')
    dirty_list = [entry.split()[-1] for entry in repo.git.diff(*default_args).splitlines()]
    return set(dirty_list) - set(repo.index.unmerged_blobs().keys())


def git_blob_from_commit(commit, path):
    git_blob = None
    for git_obj in commit.tree.list_traverse():
        if git_obj.path == path and git_obj.type == 'blob':
            git_blob = git_obj
            break
    return git_blob


def git_blob_from_index(index, path):
    git_blob = None
    for stage, git_obj in index.iter_blobs(lambda t: t[0] == 0):
        if git_obj.path == path and git_obj.type == 'blob':
            git_blob = git_obj
            break
    return git_blob


def get_recursive_node_dict(title, children):
    node_dict = {
        'title': title,
    }
    if children:
        node_dict['folder'] = True
        node_dict['expanded'] = True
        node_dict['children'] = [get_recursive_node_dict(title, children[title]) for title in children]
    return node_dict
