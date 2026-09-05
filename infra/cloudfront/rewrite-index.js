/**
 * Viewer-request rewrite for the static console.
 *
 * The bucket is served through an S3 REST origin, which resolves object keys
 * literally: a request for /console looks for a key named "console" and finds
 * nothing, because the export writes console/index.html. Only the root gets
 * index resolution, via DefaultRootObject. This maps extensionless paths onto
 * the index document so every route resolves, and so deploying stays a plain
 * `aws s3 sync --delete` with no per-file content-type juggling.
 */
function handler(event) {
  var request = event.request;
  var uri = request.uri;

  if (uri.endsWith("/")) {
    request.uri = uri + "index.html";
  } else if (!uri.split("/").pop().includes(".")) {
    request.uri = uri + "/index.html";
  }
  return request;
}
