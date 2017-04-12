# quip-python
An unoffical Quip API Python client library witten in python 3.5. This extends the official library on [Quip's github](https://github.com/quip/quip-api/tree/master/python), which seems to break often due to html parsing bugs and is written in python 2.7.

This makes installing simpler and adds some higher level functionality that is not native to the offical client library.



# Install
```
download from http://github.com/THADEUSH123/quip-python/archive/master.zip
unzip -a quip-python-master.zip
cd quip-python-master
sudo python setup.py install
cd ..
rm -r quip-python-master quip-python-master.zip
```

## Usage
### Example usage 1

```python
client = quip.QuipClient(access_token="...")
user = client.get_authenticated_user()
starred = client.get_folder(user["starred_folder_id"])
print "There are", len(starred["children"]), "items in your starred folder"
```

### Example usage 2
```python
import quip

key, doc_id, verbose = quip.get_quip_environment('config_settings.json')
print quip.dictReader(key, doc_id)

```
### get_quip_environment() usage
get_quip_environment() implements command line shortcuts for configuration information. It will accept a json encoded config file as well as command line arguments. By default, it checks for a file 'config_settings.json' with the format.
```
{
    "quip_doc_id": "this is the id in the url",
    "quip_api_key": "an api key from https://quip.com/api/personal-token"
}
```

If the config file is not used, the usage is:
```python
usage: __init__.py [-h] [-v] [--quip_api_key QUIP_API_KEY]
                   [--quip_doc_id QUIP_DOC_ID]
                   [config_file]

Convert a quip document to misc report formats.

positional arguments:
  config_file           The configuration file specs.

optional arguments:
  -h, --help            show this help message and exit
  -v, --verbose
  --quip_api_key QUIP_API_KEY API key for quip.
  --quip_doc_id QUIP_DOC_ID Quip document ID.
```
