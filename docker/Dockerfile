ARG BASE_IMAGE=docker.io/opentripplanner/opentripplanner:2.10.0
FROM ${BASE_IMAGE}

# The EAE realtime feeds redirect to s3.itbatera.euskadi.eus, whose certificate
# chain ends at the Izenpe.com root CA. That root is not part of the JDK
# truststore shipped in the official OTP image, so the GTFS-RT fetches fail with
# "PKIX path building failed". Import it to make the realtime updaters work.
#
# Izenpe.com root SHA-256:
# 25:30:CC:8E:98:32:15:02:BA:D9:6F:9B:1F:BA:1B:09:9E:2D:29:9E:0F:45:48:BB:91:4F:36:3B:C0:D4:53:1F
USER root
COPY certs/izenpe-com.crt /usr/local/share/ca-certificates/izenpe-com.crt
RUN keytool -importcert -noprompt -trustcacerts \
    -alias izenpe-com \
    -file /usr/local/share/ca-certificates/izenpe-com.crt \
    -cacerts -storepass changeit
