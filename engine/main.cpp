#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef _CRT_SECURE_NO_WARNINGS
#define _CRT_SECURE_NO_WARNINGS
#endif
#include <windows.h>
#include <winsock2.h>
#include <ws2tcpip.h>
#pragma comment(lib, "ws2_32.lib")
#pragma comment(lib, "crypt32.lib")
#endif

#include "alignment.hpp"
#include "tests/test_alignment.hpp"
#include <httplib.h>
#include <nlohmann/json.hpp>

#include <cstdlib>
#include <iostream>
#include <string>

namespace {

void set_cors_headers(httplib::Response& res) {
    res.set_header("Access-Control-Allow-Origin", "*");
    res.set_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    res.set_header("Access-Control-Allow-Headers", "Content-Type, Authorization, Accept, Origin, X-Requested-With");
}

void send_error(httplib::Response& res, int status_code, const std::string& error_code, const std::string& message) {
    set_cors_headers(res);
    nlohmann::json err_json;
    err_json["status"] = "error";
    err_json["error"] = error_code;
    err_json["message"] = message;
    res.status = status_code;
    res.set_content(err_json.dump(), "application/json");
}

} // anonymous namespace

int main(int argc, char* argv[]) {
    // If invoked with --test or -t, execute the alignment unit test suite directly
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--test" || arg == "-t") {
            return helixguard::run_alignment_tests();
        }
    }

    httplib::Server svr;

    // CORS pre-routing handler and OPTIONS preflight
    svr.set_pre_routing_handler([](const httplib::Request& req, httplib::Response& res) {
        set_cors_headers(res);
        if (req.method == "OPTIONS") {
            res.status = 200;
            return httplib::Server::HandlerResponse::Handled;
        }
        return httplib::Server::HandlerResponse::Unhandled;
    });

    // GET /health endpoint
    svr.Get("/health", [](const httplib::Request&, httplib::Response& res) {
        set_cors_headers(res);
        nlohmann::json health_json;
        health_json["status"] = "healthy";
        health_json["service"] = "helixguard-alignment-engine";
        health_json["version"] = "1.0.0";
        res.status = 200;
        res.set_content(health_json.dump(), "application/json");
    });

    // GET /test endpoint to trigger unit tests via HTTP
    svr.Get("/test", [](const httplib::Request&, httplib::Response& res) {
        set_cors_headers(res);
        int result = helixguard::run_alignment_tests();
        nlohmann::json test_json;
        test_json["status"] = (result == 0) ? "success" : "failed";
        test_json["all_tests_passed"] = (result == 0);
        res.status = (result == 0) ? 200 : 500;
        res.set_content(test_json.dump(), "application/json");
    });

    // POST /align endpoint
    svr.Post("/align", [](const httplib::Request& req, httplib::Response& res) {
        set_cors_headers(res);

        nlohmann::json body;
        try {
            body = nlohmann::json::parse(req.body);
        } catch (const nlohmann::json::parse_error& e) {
            send_error(res, 400, "MALFORMED_JSON",
                       std::string("Malformed JSON in request body: ") + e.what());
            return;
        }

        if (!body.is_object()) {
            send_error(res, 400, "INVALID_PAYLOAD", "Request body must be a JSON object.");
            return;
        }

        // Validate presence of required sequence fields
        if (!body.contains("reference_sequence") || !body.contains("query_sequence")) {
            send_error(res, 400, "MISSING_FIELDS",
                       "Missing required field(s): both 'reference_sequence' and 'query_sequence' must be provided.");
            return;
        }

        if (!body["reference_sequence"].is_string() || !body["query_sequence"].is_string()) {
            send_error(res, 400, "INVALID_TYPE",
                       "'reference_sequence' and 'query_sequence' must be strings.");
            return;
        }

        const std::string ref_seq = body["reference_sequence"].get<std::string>();
        const std::string qry_seq = body["query_sequence"].get<std::string>();

        // Empty sequence validation
        if (ref_seq.empty() || qry_seq.empty()) {
            send_error(res, 400, "EMPTY_SEQUENCE",
                       "Sequences cannot be empty. Both 'reference_sequence' and 'query_sequence' must have length > 0.");
            return;
        }

        // Sequence content and length validation
        std::string err_msg;
        if (!helixguard::is_valid_sequence(ref_seq, &err_msg)) {
            if (ref_seq.size() > 10000) {
                send_error(res, 400, "INPUT_TOO_LARGE", "reference_sequence: " + err_msg);
            } else {
                send_error(res, 400, "INVALID_CHARACTERS", "reference_sequence: " + err_msg);
            }
            return;
        }

        if (!helixguard::is_valid_sequence(qry_seq, &err_msg)) {
            if (qry_seq.size() > 10000) {
                send_error(res, 400, "INPUT_TOO_LARGE", "query_sequence: " + err_msg);
            } else {
                send_error(res, 400, "INVALID_CHARACTERS", "query_sequence: " + err_msg);
            }
            return;
        }

        // Parse optional scoring parameters
        helixguard::ScoringParams scoring;

        if (body.contains("scoring") && body["scoring"].is_object()) {
            const auto& s = body["scoring"];
            if (s.contains("match")) {
                if (!s["match"].is_number_integer()) {
                    send_error(res, 400, "INVALID_SCORING", "scoring.match must be an integer.");
                    return;
                }
                scoring.match = s["match"].get<int>();
            }
            if (s.contains("mismatch")) {
                if (!s["mismatch"].is_number_integer()) {
                    send_error(res, 400, "INVALID_SCORING", "scoring.mismatch must be an integer.");
                    return;
                }
                scoring.mismatch = s["mismatch"].get<int>();
            }
            if (s.contains("gap")) {
                if (!s["gap"].is_number_integer()) {
                    send_error(res, 400, "INVALID_SCORING", "scoring.gap must be an integer.");
                    return;
                }
                scoring.gap = s["gap"].get<int>();
            }
        } else {
            // Also accept flat scoring parameters: "match", "mismatch", "gap" (or "_score" suffix)
            if (body.contains("match") || body.contains("match_score")) {
                const char* key = body.contains("match") ? "match" : "match_score";
                if (!body[key].is_number_integer()) {
                    send_error(res, 400, "INVALID_SCORING", std::string(key) + " must be an integer.");
                    return;
                }
                scoring.match = body[key].get<int>();
            }
            if (body.contains("mismatch") || body.contains("mismatch_score")) {
                const char* key = body.contains("mismatch") ? "mismatch" : "mismatch_score";
                if (!body[key].is_number_integer()) {
                    send_error(res, 400, "INVALID_SCORING", std::string(key) + " must be an integer.");
                    return;
                }
                scoring.mismatch = body[key].get<int>();
            }
            if (body.contains("gap") || body.contains("gap_score")) {
                const char* key = body.contains("gap") ? "gap" : "gap_score";
                if (!body[key].is_number_integer()) {
                    send_error(res, 400, "INVALID_SCORING", std::string(key) + " must be an integer.");
                    return;
                }
                scoring.gap = body[key].get<int>();
            }
        }

        // Validate scoring parameters
        if (!helixguard::is_valid_scoring(scoring, &err_msg)) {
            send_error(res, 400, "INVALID_SCORING", err_msg);
            return;
        }

        // Execute Smith-Waterman alignment
        try {
            helixguard::AlignmentResult result = helixguard::align(ref_seq, qry_seq, scoring);

            nlohmann::json resp;
            resp["status"] = "success";
            resp["alignment_score"] = result.alignment_score;
            resp["max_cell"] = {
                {"row", result.max_cell.row},
                {"column", result.max_cell.column}
            };
            resp["matrix"] = result.matrix;
            resp["matrix_dimensions"] = {
                {"rows", result.rows},
                {"columns", result.columns},
                {"cols", result.columns}
            };
            resp["scoring"] = {
                {"match", result.scoring.match},
                {"mismatch", result.scoring.mismatch},
                {"gap", result.scoring.gap}
            };
            resp["traceback"] = {
                {"aligned_reference", result.traceback.aligned_reference},
                {"aligned_query", result.traceback.aligned_query}
            };

            res.status = 200;
            res.set_content(resp.dump(), "application/json");
        } catch (const std::exception& ex) {
            send_error(res, 500, "INTERNAL_ERROR",
                       std::string("Alignment execution failed: ") + ex.what());
        }
    });

    int port = 8080;
    const char* port_env = std::getenv("PORT");
    if (port_env && *port_env) {
        try {
            port = std::stoi(port_env);
        } catch (...) {
            port = 8080;
        }
    }

    std::string host = "0.0.0.0";
    const char* host_env = std::getenv("HOST");
    if (host_env && *host_env) {
        host = host_env;
    }

    std::cout << "[HelixGuard Engine] Starting HTTP server on " << host << ":" << port << std::endl;
    if (!svr.listen(host, port)) {
        std::cerr << "[HelixGuard Engine] Failed to bind/listen on port " << port << std::endl;
        return 1;
    }

    return 0;
}
