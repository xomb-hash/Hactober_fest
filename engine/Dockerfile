# Multi-stage build for HelixGuard C++ Smith-Waterman Alignment Engine
FROM alpine:3.20 AS builder

RUN apk add --no-cache g++ make cmake git

WORKDIR /build
COPY CMakeLists.txt alignment.hpp alignment.cpp main.cpp ./
COPY include/ ./include/
COPY tests/ ./tests/

RUN cmake -B build -DCMAKE_BUILD_TYPE=Release && \
    cmake --build build --config Release

# Production runtime container
FROM alpine:3.20

RUN apk add --no-cache libstdc++

WORKDIR /app
COPY --from=builder /build/build/server /app/server

ENV PORT=8080
ENV HOST=0.0.0.0

EXPOSE 8080

HEALTHCHECK --interval=5s --timeout=3s --retries=3 \
    CMD wget -q -O- http://localhost:8080/health || exit 1

ENTRYPOINT ["/app/server"]
