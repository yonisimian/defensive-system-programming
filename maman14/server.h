/**
  @file server.h
  @author Yehonatan Simian
  @date January 2024

  +-----------------------------------------------------------------------------------+
  |                      Defensive System Programming - Maman 14                      |
  |                                                                                   |
  |       "Always try to be nice, but never fail to be kind." - The 12th Doctor       |
  +-----------------------------------------------------------------------------------+

  @section DESCRIPTION ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

  This project is a server that allows clients to backup files and retrieve them later.
  The server is stateless, and supports multiple clients at the same time.

  The server supports the following client requests:
  - Save a file
  - Restore a file
  - Delete a file
  - List all files

  The server can respond with the following statuses:
  - Success: Restore
  - Success: List
  - Success: Save / Delete
  - Error: No such file
  - Error: No such client
  - Error: General error

  The server is implemented using Boost.Asio, and uses TCP sockets for communication.

  @note The server doesn't handle endianess, as for most modern systems are assumed to
        be little endian, which is the requested endianess to be used.

  @section REVISIONS ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

  - Version 1: Functioning server. No error handling, no request processing.
  - Version 2: Processing requests, minimal error handling.
  - Version 3: Support partial requests (omit redundant data).
  - Version 4: First production version. Full error handling, full request processing.
  - Version 5: clang-tidy fixes and code cleanup.
  - Version 6: Added tests, fixed small bugs.

  @section TODO ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

  - Handle client sending less data than expected.
    - Current solution: the thread waits for more data until the socket is closed.
    - Possible solution: arbitrary timeout.
  - Handle client sending more data than expected.
    - Current solution: the thread discards the extra data.
      This solution does not support clients sending few requests on the same socket.
  - Create a thread pool. It won't prevent DDoS attacks, but at least it will prevent
    clients from opening too many threads and crashing the server.

  @section COMPILATION ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

  To compile this project, I have used the following command:

  cl.exe /W4 /WX /analyze /std:c++17 /Zi /EHsc /nologo /D_WIN32_WINNT=0x0A00
         /I C:\path\to\boost "/FeC:\path\to\main.cpp"

  @copyright All rights reserved (c) Yehonatan Simian 2024 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

#pragma once

#pragma region includes
// +----------------------------------------------------------------------------------+
// | Inlcudes: Standard Library and Boost                                             |
// +----------------------------------------------------------------------------------+
#include <algorithm>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <optional>
#include <string_view>
#include <thread>

#pragma warning(push)
#pragma warning(disable : 6001 6031 6101 6255 6258 6313 6387)
#include <boost/asio.hpp>
#pragma warning(pop)
#pragma endregion

#pragma region macros
// +----------------------------------------------------------------------------------+
// | Macros & Logging Supplements                                                     |
// +----------------------------------------------------------------------------------+
namespace
{
#ifdef DEBUG
  template <typename T>
  void log(const T &t)
  {
    std::cerr << t << std::endl;
  }

  template <typename T, typename... Args>
  void log(const T &t, const Args &...args)
  {
    std::cerr << t;
    log(args...);
  }
#else
  template <typename... Args>
  void log([[maybe_unused]] const Args &...args)
  {
  }
#endif
} // anonymous namespace

#define SOCKET_IO(operation, pointer, size, error_value, ...)                                  \
  do                                                                                           \
  {                                                                                            \
    if (auto bytes_transferred = operation(socket, boost::asio::buffer(pointer, size), error); \
        error || bytes_transferred != size)                                                    \
    {                                                                                          \
      log(__VA_ARGS__);                                                                        \
      return error_value;                                                                      \
    }                                                                                          \
  } while (0)

#define SOCKET_WRITE_OR_RETURN(pointer, size, error_value, ...) \
  SOCKET_IO(boost::asio::write, pointer, size, error_value, __VA_ARGS__)

#define SOCKET_READ_OR_RETURN(pointer, size, error_value, ...) \
  SOCKET_IO(boost::asio::read, pointer, size, error_value, __VA_ARGS__)
#pragma endregion

#pragma region interface
// +----------------------------------------------------------------------------------+
// | Interface: user exposed functions and variables                                  |
// +----------------------------------------------------------------------------------+
namespace maman14
{
  static constexpr inline uint8_t server_version = 6;
  static constexpr inline std::string_view server_dir_name = "my_server";
  static void start_server_on_port(uint16_t port);
} // namespace maman14
#pragma endregion

#pragma region enums
// +----------------------------------------------------------------------------------+
// | Enums: protocol enums and relevant functions                                     |
// +----------------------------------------------------------------------------------+
namespace
{
  enum class Op : uint8_t
  {
    save = 100,
    restore = 200, // no size or payload
    remove = 201,  // no size or payload
    list = 202,    // no size, payload, name_len or filename
  };

  auto is_valid_op(uint8_t value) -> bool
  {
    return value == static_cast<uint8_t>(Op::save) ||
           value == static_cast<uint8_t>(Op::restore) ||
           value == static_cast<uint8_t>(Op::remove) ||
           value == static_cast<uint8_t>(Op::list);
  }

  enum class Status : uint16_t
  {
    success_restore = 210,
    success_list = 211,
    success_save = 212,     // no size or payload
    error_no_file = 1001,   // no size or payload
    error_no_client = 1002, // only version and status
    error_general = 1003,   // only version and status
  };
} // anonymous namespace
#pragma endregion

#pragma region implementation_protocol
// +----------------------------------------------------------------------------------+
// | Implementation of the request protocol:                                          |
// | - Request class(es), include request processing implementation.                  |
// | - Response class(es).                                                            |
// | - Common class(es) for Request and Response                                      |
// +----------------------------------------------------------------------------------+
namespace
{
#pragma pack(push, 1)

  // classes to be used by both Request and Response

  class Payload
  {
    std::vector<uint8_t> content;

  private:
    Payload(std::vector<uint8_t> content)
        : content(std::move(content)){};

  public:
    Payload() = delete;
    Payload(const Payload &) = delete;
    Payload &operator=(const Payload &) = delete;
    Payload(Payload &&) = default;
    Payload &operator=(Payload &&) = default;
    ~Payload() = default;

    static std::optional<Payload> from_vector(std::vector<uint8_t> content)
    {
      if (content.size() > std::numeric_limits<uint32_t>::max())
      {
        log("Payload is too long: ", content.size());
        return std::nullopt;
      }

      return Payload(content);
    }

    const bool write_to_socket(boost::asio::ip::tcp::socket &socket, boost::system::error_code &error) const
    {
      uint32_t size = static_cast<uint32_t>(content.size());

      SOCKET_WRITE_OR_RETURN(&size, sizeof(size), false, "Failed to write payload size: ", error.message());

      SOCKET_WRITE_OR_RETURN(content.data(), size, false, "Failed to write payload content: ", error.message());

      return true;
    };

    const bool write_to_file(const std::filesystem::path &file_path) const
    {
      std::ofstream file(file_path, std::ios::binary | std::ios::trunc);
      if (!file)
      {
        log("Failed to open file: ", file_path);
        return false;
      }

      file.write(reinterpret_cast<const char *>(content.data()), content.size());
      if (!file)
      {
        log("Failed to write to file: ", file_path);
        return false;
      }

      return true;
    }

    static const std::optional<Payload> read_from_socket(boost::asio::ip::tcp::socket &socket, boost::system::error_code &error)
    {
      uint32_t size;

      SOCKET_READ_OR_RETURN(&size, sizeof(size), {}, "Failed to read payload size: ", error.message());

      std::vector<uint8_t> content(size);

      SOCKET_READ_OR_RETURN(content.data(), size, {}, "Failed to read payload content: ", error.message());

      return std::make_optional<Payload>(std::move(content));
    };

    static const std::optional<Payload> read_from_file(const std::filesystem::path &file_path)
    {
      std::ifstream file(file_path, std::ios::binary | std::ios::ate);
      if (!file)
      {
        log("Failed to open file: ", file_path);
        return {};
      }

      std::streamsize size = file.tellg();
      file.seekg(0, std::ios::beg);

      if (size > std::numeric_limits<uint32_t>::max())
      {
        log("File size is too big: ", size);
        return {};
      }

      std::vector<uint8_t> content(static_cast<uint32_t>(size));
      file.read(reinterpret_cast<char *>(content.data()), size);
      if (!file)
      {
        log("Failed to read file: ", file_path);
        return {};
      }

      return std::make_optional<Payload>(std::move(content));
    }

    friend std::ostream &operator<<(std::ostream &os, const Payload &payload)
    {
      static constexpr uint32_t MAX_PAYLOAD_PRINT_SIZE = 69;
      const uint32_t size = payload.content.size();

      os << "payload size: " << size << '\n';
      os << (size > MAX_PAYLOAD_PRINT_SIZE ? "payload (printing limited to 69 bytes):\n" : "payload:\n")
         << std::string_view(reinterpret_cast<const char *>(payload.content.data()), std::min(size, MAX_PAYLOAD_PRINT_SIZE)) << '\n';

      return os;
    }
  };

  class Filename
  {
    std::vector<char> content;

  private:
    Filename(std::vector<char> content)
        : content(std::move(content)){};

  public:
    Filename() = delete;
    Filename(const Filename &) = delete;
    Filename &operator=(const Filename &) = delete;
    Filename(Filename &&) = default;
    Filename &operator=(Filename &&) = default;
    ~Filename() = default;

    static std::optional<Filename> from_vector(const std::vector<char> filename)
    {
      if (filename.size() > std::numeric_limits<uint16_t>::max())
      {
        log("Filename is too long: ", filename.size());
        return std::nullopt;
      }

      return Filename(filename);
    }

    const std::string_view get_name() const
    {
      return std::string_view(content.data(), content.size());
    }

    const bool write_to_socket(boost::asio::ip::tcp::socket &socket, boost::system::error_code &error) const
    {
      uint16_t name_len = static_cast<uint16_t>(content.size());

      SOCKET_WRITE_OR_RETURN(&name_len, sizeof(name_len), false, "Failed to write name_len: ", error.message());

      SOCKET_WRITE_OR_RETURN(content.data(), name_len, false, "Failed to write filename: ", error.message());

      return true;
    }

    static const std::optional<Filename> read_from_socket(boost::asio::ip::tcp::socket &socket, boost::system::error_code &error)
    {
      uint16_t name_len;

      SOCKET_READ_OR_RETURN(&name_len, sizeof(name_len), std::nullopt, "Failed to read name_len: ", error.message());

      if (name_len == 0)
      {
        log("name_len can't be 0");
        return std::nullopt;
      }

      std::vector<char> content(name_len);

      SOCKET_READ_OR_RETURN(content.data(), name_len, std::nullopt, "Failed to read filename: ", error.message());

      if (!is_filename_valid(content))
      {
        log("Invalid filename: ", content.data());
        return std::nullopt;
      }

      return std::make_optional<Filename>(std::move(content));
    }

    friend std::ostream &operator<<(std::ostream &os, const Filename &filename)
    {
      os << "name_len: " << filename.content.size() << '\n';
      os << "filename: " << filename.content.data() << '\n';
      return os;
    }

  private:
    const static bool is_filename_valid(std::vector<char> &content)
    {
      static constexpr std::initializer_list<char> forbidden_start_char = {' '};
      static constexpr std::initializer_list<char> forbidden_middle_chars = {'\0', '/', '\\', ':', '*', '?', '"', '<', '>', '|'};
      static constexpr std::initializer_list<char> forbidden_end_char = {' ', '.'};

      return std::none_of(forbidden_start_char.begin(), forbidden_start_char.end(), [&](char c) { return content[0] == c; }) &&
             std::none_of(forbidden_end_char.begin(), forbidden_end_char.end(), [&](char c) { return content[content.size() - 1] == c; }) &&
             std::none_of(content.begin(), content.end(), [&](char c) { return std::any_of(
                                                                            forbidden_middle_chars.begin(), forbidden_middle_chars.end(), [&](char f) { return f == c; }); });
    }
  };

  // forward declare Response so that it can be used in Request::process()

  class Response;

  // Requests base classes

  class Request
  {
  protected:
    const uint32_t user_id;
    const uint8_t version;
    const Op op;

    Request(uint32_t user_id, uint8_t version, Op op)
        : user_id(user_id), version(version), op(op){};

  public:
    Request(const Request &) = delete;
    Request &operator=(const Request &) = delete;
    Request(Request &&) = default;
    Request &operator=(Request &&) = default;

    virtual ~Request() = default;

    static const std::optional<std::tuple<uint32_t, uint8_t, Op>> read_user_id_and_version_and_op(boost::asio::ip::tcp::socket &socket, boost::system::error_code &error)
    {
      struct RequestData
      {
        uint32_t user_id;
        uint8_t version;
        Op op;
      };
      RequestData data;

      SOCKET_READ_OR_RETURN(&data, sizeof(data), std::nullopt, "Failed to read request: ", error.message());

      if (!is_valid_op(static_cast<uint8_t>(data.op)))
      {
        log("Invalid op: ", static_cast<uint16_t>(data.op));
        return std::nullopt;
      }

      return std::make_tuple(data.user_id, data.version, data.op);
    }

    const std::filesystem::path get_user_dir_path() const
    {
      return std::filesystem::path("C:\\") / maman14::server_dir_name / std::to_string(user_id);
    }

    virtual std::unique_ptr<Response> process() = 0; // one day son, I will const process() as well. one day.

    virtual void print(std::ostream &os) const
    {
      os << "user_id: " << user_id << '\n';
      os << "version: " << static_cast<uint16_t>(version) << '\n';
      os << "op: " << static_cast<uint16_t>(op) << '\n';
    }

    friend std::ostream &operator<<(std::ostream &os, const Request &request)
    {
      request.print(os);
      return os;
    }
  };

  class RequestWithFileName : public Request
  {
  protected:
    Filename filename; // TODO: figure why I can't const it

    RequestWithFileName(uint32_t user_id, uint8_t version, Op op, Filename filename)
        : Request(user_id, version, op), filename(std::move(filename)){};

  public:
    RequestWithFileName(const RequestWithFileName &) = delete;
    RequestWithFileName &operator=(const RequestWithFileName &) = delete;
    RequestWithFileName(RequestWithFileName &&) = default;
    RequestWithFileName &operator=(RequestWithFileName &&) = default;

    virtual ~RequestWithFileName() = default;

    const std::filesystem::path get_user_file_path(const std::filesystem::path &user_dir_path) const
    {
      return user_dir_path / filename.get_name();
    }

    virtual void print(std::ostream &os) const override
    {
      Request::print(os);
      os << filename << '\n';
    }
  };

  class RequestWithPayload : public RequestWithFileName
  {
  protected:
    const Payload payload;

    RequestWithPayload(uint32_t user_id, uint8_t version, Op op, Filename filename, Payload payload)
        : RequestWithFileName(user_id, version, op, std::move(filename)), payload(std::move(payload)){};

  public:
    RequestWithPayload(const RequestWithPayload &) = delete;
    RequestWithPayload &operator=(const RequestWithPayload &) = delete;
    RequestWithPayload(RequestWithPayload &&) = default;
    RequestWithPayload &operator=(RequestWithPayload &&) = default;

    ~RequestWithPayload() = default;

    void print(std::ostream &os) const override
    {
      RequestWithFileName::print(os);
      os << payload << '\n';
    }
  };

  // Response base classes

  class Response
  {
  protected:
    const uint8_t version;
    const Status status;

    Response(Status status)
        : version(maman14::server_version), status(status){};

  public:
    Response(const Response &) = delete;
    Response &operator=(const Response &) = delete;
    Response(Response &&) = default;
    Response &operator=(Response &&) = default;

    virtual ~Response() = default;

    virtual const bool write_to_socket(boost::asio::ip::tcp::socket &socket, boost::system::error_code &error) const
    {
      SOCKET_WRITE_OR_RETURN(&this->version, sizeof(version) + sizeof(status), false, "Failed to write response: ", error.message());

      return true;
    }

    virtual void print(std::ostream &os) const
    {
      os << "version: " << static_cast<uint16_t>(version) << '\n';
      os << "status: " << static_cast<uint16_t>(status) << '\n';
    }

    friend std::ostream &operator<<(std::ostream &os, const Response &response)
    {
      response.print(os);
      return os;
    }
  };

  class ResponseWithFileName : public Response
  {
  protected:
    const Filename filename;

    ResponseWithFileName(Status status, Filename filename)
        : Response(status), filename(std::move(filename)){};

  public:
    ResponseWithFileName(const ResponseWithFileName &) = delete;
    ResponseWithFileName &operator=(const ResponseWithFileName &) = delete;
    ResponseWithFileName(ResponseWithFileName &&) = default;
    ResponseWithFileName &operator=(ResponseWithFileName &&) = default;

    virtual ~ResponseWithFileName() = default;

    virtual const bool write_to_socket(boost::asio::ip::tcp::socket &socket, boost::system::error_code &error) const override
    {
      if (!Response::write_to_socket(socket, error))
      {
        return false;
      }

      if (!filename.write_to_socket(socket, error))
      {
        return false;
      }

      return true;
    }

    virtual void print(std::ostream &os) const override
    {
      Response::print(os);
      os << filename << '\n';
    }
  };

  class ResponseWithPayload : public ResponseWithFileName
  {
  protected:
    const Payload payload;

    ResponseWithPayload(Status status, Filename filename, Payload payload)
        : ResponseWithFileName(status, std::move(filename)), payload(std::move(payload)){};

  public:
    ResponseWithPayload(const ResponseWithPayload &) = delete;
    ResponseWithPayload &operator=(const ResponseWithPayload &) = delete;
    ResponseWithPayload(ResponseWithPayload &&) = default;
    ResponseWithPayload &operator=(ResponseWithPayload &&) = default;

    ~ResponseWithPayload() = default;

    const bool write_to_socket(boost::asio::ip::tcp::socket &socket, boost::system::error_code &error) const override
    {
      if (!ResponseWithFileName::write_to_socket(socket, error))
      {
        return false;
      }

      if (!payload.write_to_socket(socket, error))
      {
        return false;
      }

      return true;
    };

    void print(std::ostream &os) const override
    {
      ResponseWithFileName::print(os);
      os << payload << '\n';
    }
  };

  // Response concrete classes (final, non-abstract)

  class ResponseSuccessRestore final : public ResponseWithPayload
  {
  public:
    explicit ResponseSuccessRestore(Filename filename, Payload payload)
        : ResponseWithPayload(Status::success_restore, std::move(filename), std::move(payload)){};
  };

  class ResponseSuccessList final : public ResponseWithPayload
  {
  public:
    explicit ResponseSuccessList(Filename filename, Payload payload)
        : ResponseWithPayload(Status::success_list, std::move(filename), std::move(payload)){};
  };

  class ResponseSuccessSave final : public ResponseWithFileName
  {
  public:
    explicit ResponseSuccessSave(Filename filename)
        : ResponseWithFileName(Status::success_save, std::move(filename)){};
  };

  class ResponseErrorNoFile final : public ResponseWithFileName
  {
  public:
    explicit ResponseErrorNoFile(Filename filename)
        : ResponseWithFileName(Status::error_no_file, std::move(filename)){};
  };

  class ResponseErrorNoClient final : public Response
  {
  public:
    explicit ResponseErrorNoClient()
        : Response(Status::error_no_client){};
  };

  class ResponseErrorGeneral final : public Response
  {
  public:
    explicit ResponseErrorGeneral()
        : Response(Status::error_general){};
  };

  // Request concrete classs (final, non-abstract)

  class RequestSave final : public RequestWithPayload
  {
  public:
    explicit RequestSave(uint32_t user_id, uint8_t version, Filename filename, Payload payload)
        : RequestWithPayload(user_id, version, Op::save, std::move(filename), std::move(payload)){};

    std::unique_ptr<Response> process() override
    {
      auto dir_path = get_user_dir_path();

      std::filesystem::create_directories(dir_path);

      auto file_path = get_user_file_path(dir_path);
      if (!payload.write_to_file(file_path))
      {
        return std::make_unique<ResponseErrorGeneral>();
      }

      return std::make_unique<ResponseSuccessSave>(std::move(filename));
    }
  };

  class RequestRestore final : public RequestWithFileName
  {
  public:
    explicit RequestRestore(uint32_t user_id, uint8_t version, Filename filename)
        : RequestWithFileName(user_id, version, Op::restore, std::move(filename)){};

    std::unique_ptr<Response> process() override
    {
      auto dir_path = get_user_dir_path();
      if (!std::filesystem::exists(dir_path) || std::filesystem::is_empty(dir_path))
      {
        return std::make_unique<ResponseErrorNoClient>();
      }

      auto file_path = get_user_file_path(dir_path);
      if (!std::filesystem::exists(file_path))
      {
        return std::make_unique<ResponseErrorNoFile>(std::move(filename));
      }

      auto payload = Payload::read_from_file(file_path);
      if (!payload)
      {
        return std::make_unique<ResponseErrorNoFile>(std::move(filename));
      }

      return std::make_unique<ResponseSuccessRestore>(std::move(filename), std::move(payload.value()));
    }
  };

  class RequestDelete final : public RequestWithFileName
  {
  public:
    explicit RequestDelete(uint32_t user_id, uint8_t version, Filename filename)
        : RequestWithFileName(user_id, version, Op::remove, std::move(filename)){};

    std::unique_ptr<Response> process() override
    {
      auto dir_path = get_user_dir_path();
      if (!std::filesystem::exists(dir_path) || std::filesystem::is_empty(dir_path))
      {
        return std::make_unique<ResponseErrorNoClient>();
      }

      auto file_path = get_user_file_path(dir_path);
      if (!std::filesystem::exists(file_path))
      {
        return std::make_unique<ResponseErrorNoFile>(std::move(filename));
      }

      if (std::error_code ec; !std::filesystem::remove(file_path, ec))
      {
        log("Failed to delete file: ", file_path);
        return std::make_unique<ResponseErrorGeneral>();
      }

      return std::make_unique<ResponseSuccessSave>(std::move(filename));
    }
  };

  class RequestList final : public Request
  {
  public:
    explicit RequestList(uint32_t user_id, uint8_t version)
        : Request(user_id, version, Op::list){};

    std::unique_ptr<Response> process() override
    {
      std::filesystem::path user_dir_path = get_user_dir_path();
      if (!std::filesystem::exists(user_dir_path) || std::filesystem::is_empty(user_dir_path))
      {
        return std::make_unique<ResponseErrorNoClient>();
      }

      const auto user_file_name = generate_random_file_name();

      auto filename = Filename::from_vector(user_file_name);
      if (!filename)
      {
        return std::make_unique<ResponseErrorGeneral>();
      }

      auto payload = create_payload(user_dir_path);
      if (!payload)
      {
        return std::make_unique<ResponseErrorGeneral>();
      }

      return std::make_unique<ResponseSuccessList>(std::move(filename.value()), std::move(payload.value()));
    }

  private:
    const std::vector<char> generate_random_file_name() const
    {
      static constexpr uint16_t length = 32;
      auto generate_random_character = []() -> char {
        static constexpr std::string_view characters = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";
        return characters[rand() % characters.size()];
      };
      std::vector<char> random_string(length, 0);
      std::generate_n(random_string.begin(), length, generate_random_character);
      return random_string;
    }

    const std::optional<Payload> create_payload(const std::filesystem::path &src_path) const
    {
      std::vector<uint8_t> content_vector;

      for (const auto &entry : std::filesystem::directory_iterator(src_path))
      {
        auto filename = entry.path().filename().string();
        content_vector.insert(content_vector.end(), filename.begin(), filename.end());
        content_vector.push_back('\n');
      }

      return Payload::from_vector(std::move(content_vector));
    }
  };
#pragma pack(pop)
} // anonymous namespace
#pragma endregion

#pragma region implementation_server
// +----------------------------------------------------------------------------------+
// | Implementation of the server, which should not be protocol dependent             |
// +----------------------------------------------------------------------------------+
namespace
{
  std::unique_ptr<Request> read_request(boost::asio::ip::tcp::socket &socket, boost::system::error_code &error)
  {
    // Read the common part of the request
    auto user_id_and_version_and_op = Request::read_user_id_and_version_and_op(socket, error);
    if (!user_id_and_version_and_op)
    {
      return {};
    }

    auto &[user_id, version, op] = *user_id_and_version_and_op;

    // Interpret each request type according to the op
    if (op == Op::list)
    {
      return std::make_unique<RequestList>(user_id, version);
    }
    if (op == Op::restore || op == Op::remove || op == Op::save)
    {
      auto filename = Filename::read_from_socket(socket, error);
      if (!filename)
      {
        return {};
      }

      if (op == Op::restore)
      {
        return std::make_unique<RequestRestore>(user_id, version, std::move(filename.value()));
      }
      else if (op == Op::remove)
      {
        return std::make_unique<RequestDelete>(user_id, version, std::move(filename.value()));
      }
      else
      {
        auto payload = Payload::read_from_socket(socket, error);
        if (!payload)
        {
          return {};
        }

        return std::make_unique<RequestSave>(user_id, version, std::move(filename.value()), std::move(payload.value()));
      }
    }

    return {};
  }

  const bool clear_socket(boost::asio::ip::tcp::socket &socket, boost::system::error_code &error)
  {
    boost::asio::streambuf discard_buffer;
    while (socket.available())
    {
      socket.read_some(discard_buffer.prepare(socket.available()), error);
      discard_buffer.commit(socket.available());
      if (error)
      {
        return false;
      }
    }
    return true;
  }

  void send_general_error(boost::asio::ip::tcp::socket &socket, boost::system::error_code &error)
  {
    ResponseErrorGeneral response{};
    if (!response.write_to_socket(socket, error))
    {
      log("Failed to send general response: ", error.message());
    }
    else
    {
      log("General error sent successfully :D");
    }
  }

  bool handle_request(boost::asio::ip::tcp::socket &socket, boost::system::error_code &error)
  {
    log("Receiving request :)");
    auto request = read_request(socket, error);
    if (!request)
    {
      log("Request reading failed!");
      clear_socket(socket, error);
      return false;
    }
    log(*request);

    if (socket.available())
    {
      log("Socket had redundant data. Discarding it.");
      if (!clear_socket(socket, error))
      {
        log("Failed to discard extra data: ", error.message());
      }
    }

    log("Request received. Generating response:");
    auto response = request->process();
    if (!response)
    {
      log("Request processing failed!");
      return false;
    }
    log(*response);

    log("Sending response:");
    if (!response->write_to_socket(socket, error))
    {
      log("Failed to send response: ", error.message());
      return false;
    }
    log("Response sent successfully :D");

    return true;
  }

  void handle_client(boost::asio::ip::tcp::socket socket)
  {
    boost::system::error_code error;

    try
    {
      if (!handle_request(socket, error))
      {
        send_general_error(socket, error);
      }
    }
    catch ([[maybe_unused]] std::exception &e)
    {
      log("Exception caught: ", e.what());
      send_general_error(socket, error);
    }
  }
} // anonymous namespace
#pragma endregion

#pragma region implementation_interface
// +----------------------------------------------------------------------------------+
// | Implementation of the functions that were declared on #pragma interface          |
// +----------------------------------------------------------------------------------+
namespace maman14
{
  static void start_server_on_port(uint16_t port)
  {
    using boost::asio::ip::tcp;

    try
    {
      boost::asio::io_context io_context;
      tcp::socket socket(io_context);
      tcp::acceptor acceptor(io_context, tcp::endpoint(tcp::v4(), port));

      while (true)
      {
        acceptor.accept(socket);

        std::thread(handle_client, std::move(socket)).detach();
      }
    }
    catch ([[maybe_unused]] std::exception &e)
    {
      log("Terminating server because of the following exception: ", e.what());
    }
  }

} // namespace maman14
#pragma endregion

#pragma region cleanup
// +----------------------------------------------------------------------------------+
// | Cleanup: undefine macros and re-define logging                                   |
// +----------------------------------------------------------------------------------+
#undef SOCKET_IO
#undef SOCKET_WRITE_OR_RETURN
#undef SOCKET_READ_OR_RETURN
#pragma endregion