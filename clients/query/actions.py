import json
from restle import actions

from ..utils.geometry import Extent
from ..utils.geometry import SpatialReference


class QueryAction(actions.Action):
    """ Perform a query on a feature service layer """

    def prepare_params(self, params):
        """ Serializes extent, dictionary, and list parameter values as JSON """

        for k, v in params.items():
            if isinstance(v, (SpatialReference, Extent)):
                params[k] = v.as_json_string()
            elif isinstance(v, (dict, list)):
                params[k] = json.dumps(v)
        return super(QueryAction, self).prepare_params(params)
