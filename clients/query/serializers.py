from restle.serializers import JSONSerializer
from parserutils.elements import element_to_object


class XMLToJSONSerializer(JSONSerializer):
    """ Deserializes XML as though it were JSON """

    @staticmethod
    def to_dict(s):
        root, data = element_to_object(s)
        return data[root]
