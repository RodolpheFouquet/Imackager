# How this script works

It is only accessible from localhost, on the port 5000, to check if it
is running, check if http://localhost:5000/ responds.

# Input

Call the url http://localhost:5000 using the HTTP method POST. The body
is "Content-Type: application/json" and the required json follow the
specification given by the ACM.

# Output

The processing time may take some time (since the transcoder will take
some time processing the lower resolutions).

The packaged content will be available in /var/www/dash/$assetId. The
$assetId is the assetId provided by the ACM when calling Imackager.

# Caveats

* Since the processing time may be long to encode the lower resolutions,
please, ensure that you have a timeout sufficient enough to accomodate
that.

* Currently, since the definitive signer video and AD files aren't
  available, the audio and audio metadata are not processed.


