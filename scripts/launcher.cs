using System;
using System.IO;
using System.Diagnostics;
using System.Threading;
using System.Net;
using System.Text.RegularExpressions;

namespace LegalCaseCompanion
{
    class Program
    {
        private static Process backendProcess = null;
        private static Process frontendProcess = null;
        private static Process tunnelProcess = null;
        private static string publicTunnelUrl = null;
        private static bool isExiting = false;
        private static readonly object exitLock = new object();

        static void Main(string[] args)
        {
            Console.Title = "Legal Case Companion — Full-Stack Server";
            Console.OutputEncoding = System.Text.Encoding.UTF8;

            PrintBanner();

            // Locate project root
            string projectRoot = FindProjectRoot();
            if (string.IsNullOrEmpty(projectRoot))
            {
                PrintError("Could not locate project root directory (must contain 'app' and 'frontend').");
                Console.WriteLine("Press any key to exit...");
                Console.ReadKey();
                return;
            }

            PrintInfo("Project Root: " + projectRoot);

            // Locate Python
            string pythonExe = FindPython(projectRoot);
            if (string.IsNullOrEmpty(pythonExe))
            {
                PrintError("Python not found. Please install Python 3.11+ or create a .venv.");
                Console.WriteLine("Press any key to exit...");
                Console.ReadKey();
                return;
            }
            PrintSuccess("Python Executable: " + pythonExe);

            // Locate npm
            string npmExe = FindNpm();
            if (string.IsNullOrEmpty(npmExe))
            {
                PrintError("npm not found. Please install Node.js (which includes npm).");
                Console.WriteLine("Press any key to exit...");
                Console.ReadKey();
                return;
            }
            PrintSuccess("npm Executable: " + npmExe);

            // Locate cloudflared
            string cloudflaredExe = FindCloudflared(projectRoot);
            if (!string.IsNullOrEmpty(cloudflaredExe))
            {
                PrintSuccess("Cloudflare Tunnel: " + cloudflaredExe);
            }
            else
            {
                PrintWarning("cloudflared.exe not found. Public dual-device URL will not be created.");
            }

            // Clean up any lingering processes on ports 3000 and 8000
            CleanupZombies();

            // Hook exit handlers
            Console.CancelKeyPress += new ConsoleCancelEventHandler(OnCancelKeyPress);
            AppDomain.CurrentDomain.ProcessExit += new EventHandler(OnProcessExit);

            // Start Backend
            PrintSection("1. Starting Backend (FastAPI on Port 8000)...");
            StartBackend(pythonExe, projectRoot);

            // Start Frontend
            PrintSection("2. Starting Frontend (Next.js on Port 3000)...");
            StartFrontend(npmExe, Path.Combine(projectRoot, "frontend"));

            // Start Cloudflare Tunnel
            if (!string.IsNullOrEmpty(cloudflaredExe))
            {
                PrintSection("3. Starting Cloudflare Tunnel for Cross-Device Access...");
                StartTunnel(cloudflaredExe, "http://localhost:3000");
            }

            // Wait for services to be ready
            PrintSection("4. Waiting for services to become healthy...");
            bool backendReady = WaitForUrl("http://127.0.0.1:8000/api/v1/health", 30);
            if (backendReady)
            {
                PrintSuccess("Backend API is UP and Healthy (http://127.0.0.1:8000)");
            }
            else
            {
                PrintWarning("Backend health check timed out. It may still be initializing...");
            }

            bool frontendReady = WaitForUrl("http://localhost:3000", 45);
            if (frontendReady)
            {
                PrintSuccess("Frontend UI is UP and Ready (http://localhost:3000)");
            }
            else
            {
                PrintWarning("Frontend server timed out or is still building pages...");
            }

            if (!string.IsNullOrEmpty(cloudflaredExe) && tunnelProcess != null)
            {
                PrintInfo("Waiting for public tunnel URL to generate...");
                int waitCount = 0;
                while (string.IsNullOrEmpty(publicTunnelUrl) && waitCount < 15)
                {
                    Thread.Sleep(1000);
                    waitCount++;
                }
            }

            // Open browser with public URL
            if (frontendReady || backendReady)
            {
                string launchUrl = !string.IsNullOrEmpty(publicTunnelUrl) ? publicTunnelUrl : "http://localhost:3000";
                PrintSection("5. Launching Application in Default Browser (" + launchUrl + ")...");
                try
                {
                    Process.Start(launchUrl);
                }
                catch
                {
                    try
                    {
                        Process.Start(new ProcessStartInfo("cmd", "/c start " + launchUrl) { CreateNoWindow = true });
                    }
                    catch { }
                }
            }

            PrintDashboard();

            // Interactive loop
            while (!isExiting)
            {
                try
                {
                    if (!Console.IsInputRedirected && Console.KeyAvailable)
                    {
                        ConsoleKeyInfo key = Console.ReadKey(true);
                        if (key.Key == ConsoleKey.Q)
                        {
                            Console.WriteLine("\n[EXIT] Quit command received. Shutting down...");
                            Shutdown();
                            break;
                        }
                        else if (key.Key == ConsoleKey.U)
                        {
                            if (!string.IsNullOrEmpty(publicTunnelUrl))
                            {
                                Console.WriteLine("\n[NAV] Opening Public URL: " + publicTunnelUrl);
                                Process.Start(publicTunnelUrl);
                            }
                            else
                            {
                                Console.WriteLine("\n[WARN] Public URL not available.");
                            }
                        }
                        else if (key.Key == ConsoleKey.B)
                        {
                            Console.WriteLine("\n[NAV] Opening Swagger API Documentation...");
                            Process.Start("http://127.0.0.1:8000/docs");
                        }
                        else if (key.Key == ConsoleKey.F)
                        {
                            Console.WriteLine("\n[NAV] Opening Frontend Application...");
                            Process.Start("http://localhost:3000");
                        }
                        else if (key.Key == ConsoleKey.M)
                        {
                            Console.WriteLine("\n[NAV] Opening Client & Lawyer Messages Page...");
                            Process.Start("http://localhost:3000/messages");
                        }
                        else if (key.Key == ConsoleKey.C)
                        {
                            try { Console.Clear(); } catch { }
                            PrintBanner();
                            PrintDashboard();
                        }
                    }
                }
                catch
                {
                    // Headless or redirected input environment
                }
                Thread.Sleep(500);
            }
        }

        private static void StartBackend(string pythonExe, string workingDir)
        {
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = pythonExe;
                psi.Arguments = "-m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload";
                psi.WorkingDirectory = workingDir;
                psi.UseShellExecute = false;
                psi.RedirectStandardOutput = true;
                psi.RedirectStandardError = true;
                psi.CreateNoWindow = true;

                backendProcess = new Process();
                backendProcess.StartInfo = psi;
                backendProcess.OutputDataReceived += new DataReceivedEventHandler((s, e) =>
                {
                    if (!string.IsNullOrEmpty(e.Data))
                    {
                        Console.ForegroundColor = ConsoleColor.DarkCyan;
                        Console.WriteLine("[BACKEND] " + e.Data);
                        Console.ResetColor();
                    }
                });
                backendProcess.ErrorDataReceived += new DataReceivedEventHandler((s, e) =>
                {
                    if (!string.IsNullOrEmpty(e.Data))
                    {
                        Console.ForegroundColor = ConsoleColor.DarkGray;
                        Console.WriteLine("[BACKEND] " + e.Data);
                        Console.ResetColor();
                    }
                });

                backendProcess.Start();
                backendProcess.BeginOutputReadLine();
                backendProcess.BeginErrorReadLine();
                PrintSuccess("Backend process spawned (PID: " + backendProcess.Id + ")");
            }
            catch (Exception ex)
            {
                PrintError("Failed to start backend: " + ex.Message);
            }
        }

        private static void StartFrontend(string npmExe, string workingDir)
        {
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = npmExe;
                psi.Arguments = "run dev";
                psi.WorkingDirectory = workingDir;
                psi.UseShellExecute = false;
                psi.RedirectStandardOutput = true;
                psi.RedirectStandardError = true;
                psi.CreateNoWindow = true;

                frontendProcess = new Process();
                frontendProcess.StartInfo = psi;
                frontendProcess.OutputDataReceived += new DataReceivedEventHandler((s, e) =>
                {
                    if (!string.IsNullOrEmpty(e.Data))
                    {
                        Console.ForegroundColor = ConsoleColor.DarkYellow;
                        Console.WriteLine("[FRONTEND] " + e.Data);
                        Console.ResetColor();
                    }
                });
                frontendProcess.ErrorDataReceived += new DataReceivedEventHandler((s, e) =>
                {
                    if (!string.IsNullOrEmpty(e.Data))
                    {
                        Console.ForegroundColor = ConsoleColor.DarkGray;
                        Console.WriteLine("[FRONTEND] " + e.Data);
                        Console.ResetColor();
                    }
                });

                frontendProcess.Start();
                frontendProcess.BeginOutputReadLine();
                frontendProcess.BeginErrorReadLine();
                PrintSuccess("Frontend process spawned (PID: " + frontendProcess.Id + ")");
            }
            catch (Exception ex)
            {
                PrintError("Failed to start frontend: " + ex.Message);
            }
        }

        private static void StartTunnel(string cloudflaredExe, string localUrl)
        {
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = cloudflaredExe;
                psi.Arguments = "tunnel --url " + localUrl;
                psi.UseShellExecute = false;
                psi.RedirectStandardOutput = true;
                psi.RedirectStandardError = true;
                psi.CreateNoWindow = true;

                tunnelProcess = new Process();
                tunnelProcess.StartInfo = psi;

                DataReceivedEventHandler handler = new DataReceivedEventHandler(delegate(object s, DataReceivedEventArgs e)
                {
                    if (!string.IsNullOrEmpty(e.Data))
                    {
                        if (publicTunnelUrl == null && e.Data.Contains(".trycloudflare.com"))
                        {
                            Match m = Regex.Match(e.Data, @"https://[a-zA-Z0-9-]+\.trycloudflare\.com");
                            if (m.Success)
                            {
                                publicTunnelUrl = m.Value;
                                PrintSuccess("Public Tunnel Created: " + publicTunnelUrl);
                            }
                        }
                    }
                });

                tunnelProcess.OutputDataReceived += handler;
                tunnelProcess.ErrorDataReceived += handler;

                tunnelProcess.Start();
                tunnelProcess.BeginOutputReadLine();
                tunnelProcess.BeginErrorReadLine();
                PrintSuccess("Cloudflare tunnel process spawned (PID: " + tunnelProcess.Id + ")");
            }
            catch (Exception ex)
            {
                PrintWarning("Failed to start Cloudflare tunnel: " + ex.Message);
            }
        }

        private static string FindCloudflared(string projectRoot)
        {
            string[] possiblePaths = new string[]
            {
                Path.Combine(projectRoot, "cloudflared.exe"),
                @"C:\Program Files (x86)\cloudflared\cloudflared.exe",
                @"C:\Program Files\cloudflared\cloudflared.exe",
                Environment.ExpandEnvironmentVariables(@"%LOCALAPPDATA%\cloudflared\cloudflared.exe"),
                Environment.ExpandEnvironmentVariables(@"%ProgramFiles(x86)%\cloudflared\cloudflared.exe"),
                Environment.ExpandEnvironmentVariables(@"%ProgramFiles%\cloudflared\cloudflared.exe"),
                "cloudflared.exe"
            };

            foreach (string p in possiblePaths)
            {
                try
                {
                    if (File.Exists(p)) return Path.GetFullPath(p);
                }
                catch { }
            }

            try
            {
                ProcessStartInfo psi = new ProcessStartInfo("where.exe", "cloudflared.exe")
                {
                    RedirectStandardOutput = true,
                    UseShellExecute = false,
                    CreateNoWindow = true
                };
                using (Process proc = Process.Start(psi))
                {
                    string outStr = proc.StandardOutput.ReadLine();
                    proc.WaitForExit(1000);
                    if (!string.IsNullOrEmpty(outStr) && File.Exists(outStr.Trim()))
                    {
                        return outStr.Trim();
                    }
                }
            }
            catch { }

            return null;
        }

        private static bool WaitForUrl(string url, int timeoutSeconds)
        {
            DateTime start = DateTime.Now;
            while ((DateTime.Now - start).TotalSeconds < timeoutSeconds)
            {
                try
                {
                    HttpWebRequest request = (HttpWebRequest)WebRequest.Create(url);
                    request.Timeout = 2000;
                    request.Method = "GET";
                    using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
                    {
                        if ((int)response.StatusCode >= 200 && (int)response.StatusCode < 400)
                        {
                            return true;
                        }
                    }
                }
                catch
                {
                    // server not responding yet
                }
                Thread.Sleep(1000);
            }
            return false;
        }

        private static string FindProjectRoot()
        {
            string current = AppDomain.CurrentDomain.BaseDirectory;
            for (int i = 0; i < 5; i++)
            {
                if (Directory.Exists(Path.Combine(current, "app")) && Directory.Exists(Path.Combine(current, "frontend")))
                {
                    return Path.GetFullPath(current);
                }
                if (Directory.Exists(Path.Combine(current, "lcc_saved_latest", "app")) && Directory.Exists(Path.Combine(current, "lcc_saved_latest", "frontend")))
                {
                    return Path.GetFullPath(Path.Combine(current, "lcc_saved_latest"));
                }
                string parent = Path.GetDirectoryName(current);
                if (string.IsNullOrEmpty(parent) || parent == current) break;
                current = parent;
            }

            string cd = Directory.GetCurrentDirectory();
            if (Directory.Exists(Path.Combine(cd, "app")) && Directory.Exists(Path.Combine(cd, "frontend")))
            {
                return Path.GetFullPath(cd);
            }
            if (Directory.Exists(Path.Combine(cd, "lcc_saved_latest", "app")) && Directory.Exists(Path.Combine(cd, "lcc_saved_latest", "frontend")))
            {
                return Path.GetFullPath(Path.Combine(cd, "lcc_saved_latest"));
            }

            return null;
        }

        private static string FindPython(string projectRoot)
        {
            string[] possiblePaths = new string[]
            {
                Path.Combine(projectRoot, ".venv", "Scripts", "python.exe"),
                Path.Combine(projectRoot, "venv", "Scripts", "python.exe"),
                Environment.ExpandEnvironmentVariables(@"%APPDATA%\uv\python\cpython-3.12-windows-x86_64-none\python.exe"),
                Environment.ExpandEnvironmentVariables(@"%LOCALAPPDATA%\Programs\Python\Python312\python.exe"),
                @"C:\Users\akuma\AppData\Local\Programs\Python\Python312\python.exe",
                "python.exe",
                "python"
            };

            foreach (string p in possiblePaths)
            {
                try
                {
                    if (File.Exists(p) && !p.Contains("WindowsApps")) return Path.GetFullPath(p);
                    if (p.StartsWith("python"))
                    {
                        ProcessStartInfo psi = new ProcessStartInfo("where.exe", "python")
                        {
                            RedirectStandardOutput = true,
                            UseShellExecute = false,
                            CreateNoWindow = true
                        };
                        using (Process proc = Process.Start(psi))
                        {
                            string line;
                            while ((line = proc.StandardOutput.ReadLine()) != null)
                            {
                                line = line.Trim();
                                if (!string.IsNullOrEmpty(line) && File.Exists(line) && !line.Contains("WindowsApps"))
                                {
                                    return line;
                                }
                            }
                        }
                    }
                }
                catch { }
            }
            return null;
        }

        private static string FindNpm()
        {
            string winGetBase = Environment.ExpandEnvironmentVariables(@"%LOCALAPPDATA%\Microsoft\WinGet\Packages");
            if (Directory.Exists(winGetBase))
            {
                try
                {
                    string[] npmMatches = Directory.GetFiles(winGetBase, "npm.cmd", SearchOption.AllDirectories);
                    if (npmMatches.Length > 0 && File.Exists(npmMatches[0]))
                    {
                        return npmMatches[0];
                    }
                }
                catch { }
            }

            string[] possiblePaths = new string[]
            {
                @"C:\Program Files\nodejs\npm.cmd",
                @"C:\Program Files (x86)\nodejs\npm.cmd",
                Environment.ExpandEnvironmentVariables(@"%APPDATA%\npm\npm.cmd"),
                "npm.cmd"
            };

            foreach (string p in possiblePaths)
            {
                if (File.Exists(p)) return p;
            }

            try
            {
                ProcessStartInfo psi = new ProcessStartInfo("where.exe", "npm.cmd")
                {
                    RedirectStandardOutput = true,
                    UseShellExecute = false,
                    CreateNoWindow = true
                };
                using (Process proc = Process.Start(psi))
                {
                    string outStr = proc.StandardOutput.ReadLine();
                    proc.WaitForExit(1000);
                    if (!string.IsNullOrEmpty(outStr) && File.Exists(outStr.Trim()))
                    {
                        return outStr.Trim();
                    }
                }
            }
            catch { }

            return "npm.cmd";
        }

        private static void CleanupZombies()
        {
            try
            {
                PrintInfo("Cleaning up any existing zombie processes on ports 3000 and 8000...");
                KillProcessesOnPort(3000);
                KillProcessesOnPort(8000);
                KillProcessByName("cloudflared");
            }
            catch { }
        }

        private static void KillProcessesOnPort(int port)
        {
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo("cmd", "/c netstat -aon | findstr :" + port)
                {
                    RedirectStandardOutput = true,
                    UseShellExecute = false,
                    CreateNoWindow = true
                };
                using (Process proc = Process.Start(psi))
                {
                    string output = proc.StandardOutput.ReadToEnd();
                    proc.WaitForExit(3000);
                    int currentPid = Process.GetCurrentProcess().Id;
                    foreach (string line in output.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries))
                    {
                        if (line.Contains(":" + port) && (line.Contains("LISTENING") || line.Contains("LISTEN")))
                        {
                            string[] parts = Regex.Split(line.Trim(), @"\s+");
                            if (parts.Length >= 5)
                            {
                                int pid;
                                if (int.TryParse(parts[parts.Length - 1], out pid) && pid > 0 && pid != currentPid)
                                {
                                    try
                                    {
                                        Process p = Process.GetProcessById(pid);
                                        KillProcessTree(p);
                                        PrintInfo("Cleaned up lingering process (PID " + pid + ") on port " + port);
                                    }
                                    catch { }
                                }
                            }
                        }
                    }
                }
            }
            catch { }
        }

        private static void KillProcessByName(string processName)
        {
            try
            {
                foreach (Process p in Process.GetProcessesByName(processName))
                {
                    try { p.Kill(); } catch { }
                }
            }
            catch { }
        }

        private static void Shutdown()
        {
            lock (exitLock)
            {
                if (isExiting) return;
                isExiting = true;

                PrintSection("Shutting down processes gracefully...");

                KillProcessTree(backendProcess);
                KillProcessTree(frontendProcess);
                KillProcessTree(tunnelProcess);

                PrintSuccess("All server processes stopped cleanly.");
            }
        }

        private static void KillProcessTree(Process proc)
        {
            if (proc == null) return;
            try
            {
                if (!proc.HasExited)
                {
                    ProcessStartInfo psi = new ProcessStartInfo("taskkill", "/F /T /PID " + proc.Id)
                    {
                        CreateNoWindow = true,
                        UseShellExecute = false
                    };
                    Process.Start(psi).WaitForExit(3000);
                }
            }
            catch { }
        }

        private static void OnCancelKeyPress(object sender, ConsoleCancelEventArgs e)
        {
            e.Cancel = true;
            Console.WriteLine("\n[INTERRUPT] Received Ctrl+C. Shutting down servers...");
            Shutdown();
            Environment.Exit(0);
        }

        private static void OnProcessExit(object sender, EventArgs e)
        {
            Shutdown();
        }

        private static void PrintBanner()
        {
            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine("===============================================================================");
            Console.WriteLine("           LEGAL CASE COMPANION (LCC) — FULL-STACK SYSTEM LAUNCHER            ");
            Console.WriteLine("        B2B Legal SaaS Platform for Commercial Litigation & Arbitration        ");
            Console.WriteLine("===============================================================================");
            Console.ResetColor();
        }

        private static void PrintDashboard()
        {
            Console.WriteLine();
            Console.ForegroundColor = ConsoleColor.Green;
            Console.WriteLine("===============================================================================");
            Console.WriteLine(" [ONLINE] FULL-STACK SYSTEM READY & OPERATIONAL");
            Console.WriteLine("===============================================================================");
            Console.ResetColor();
            if (!string.IsNullOrEmpty(publicTunnelUrl))
            {
                Console.ForegroundColor = ConsoleColor.Cyan;
                Console.WriteLine("  • Public Device URL (Any Device) : " + publicTunnelUrl);
                Console.ResetColor();
            }
            else
            {
                Console.ForegroundColor = ConsoleColor.DarkYellow;
                Console.WriteLine("  • Public Device URL              : [Connecting or Not Installed]");
                Console.ResetColor();
            }
            Console.WriteLine("  • Localhost Web Application      : http://localhost:3000");
            Console.WriteLine("  • Lawyer / Client Messages       : http://localhost:3000/messages");
            Console.WriteLine("  • Backend REST API               : http://127.0.0.1:8000");
            Console.WriteLine("  • OpenAPI Swagger Docs           : http://127.0.0.1:8000/docs");
            Console.WriteLine("-------------------------------------------------------------------------------");
            Console.ForegroundColor = ConsoleColor.Yellow;
            Console.WriteLine(" Hotkeys:");
            Console.WriteLine("  [U] Open Public URL   [F] Open Localhost   [B] Open Backend Docs");
            Console.WriteLine("  [M] Open Messages     [C] Clear Console    [Q] Stop & Exit");
            Console.WriteLine("===============================================================================");
            Console.ResetColor();
            Console.WriteLine();
        }

        private static void PrintSection(string text)
        {
            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine("\n--> " + text);
            Console.ResetColor();
        }

        private static void PrintSuccess(string text)
        {
            Console.ForegroundColor = ConsoleColor.Green;
            Console.WriteLine("  [OK] " + text);
            Console.ResetColor();
        }

        private static void PrintWarning(string text)
        {
            Console.ForegroundColor = ConsoleColor.Yellow;
            Console.WriteLine("  [WARN] " + text);
            Console.ResetColor();
        }

        private static void PrintError(string text)
        {
            Console.ForegroundColor = ConsoleColor.Red;
            Console.WriteLine("  [ERROR] " + text);
            Console.ResetColor();
        }

        private static void PrintInfo(string text)
        {
            Console.ForegroundColor = ConsoleColor.White;
            Console.WriteLine("  [INFO] " + text);
            Console.ResetColor();
        }
    }
}
