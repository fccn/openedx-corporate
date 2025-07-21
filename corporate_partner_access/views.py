"""Generic views for the corporate partner access."""

from os.path import dirname, realpath
from subprocess import CalledProcessError, check_output

from django.http import JsonResponse

from corporate_partner_access import __version__ as plugin_version


def info_view(request):
    """
    Provide basic information about the plugin.

    This view returns a JSON response with the version of the plugin and the git commit hash.
    """
    try:
        working_dir = dirname(realpath(__file__))
        git_data = check_output(["git", "rev-parse", "HEAD"], cwd=working_dir)
        git_data = git_data.decode().rstrip('\r\n')
    except CalledProcessError:
        git_data = ""

    response_data = {
        "version": plugin_version,
        "name": "corporate-partner-access",
        "git": git_data,
    }

    return JsonResponse(response_data)
