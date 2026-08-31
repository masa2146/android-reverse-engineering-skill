// ImportExtracted.cs — rebuild prefabs from a clone-app Unity extraction.
//
// Drop this into Assets/Editor/ and run: Tools > Clone App > Import Extracted Assets.
// Point it at a `game-assets/` directory produced by unity-extract.py. It reads
// every entities/<Name>/entity.json and recreates the object as a prefab with
// its meshes, material values, colliders, rigidbody and joints applied.
//
// It deliberately does NOT try to reproduce the original's custom scripts:
// MonoBehaviour field values are stripped in an IL2CPP release build and are
// not in the extraction. Script *names* are listed on each prefab in a
// ExtractedEntityNote component so you know what to reimplement.
#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

public class ExtractedEntityNote : MonoBehaviour
{
    [TextArea(2, 12)] public string sourceEntity;
    [TextArea(2, 12)] public string originalScripts;
    [TextArea(2, 12)] public string notes;
}

public class ImportExtracted : EditorWindow
{
    private string sourceDir = "";
    private string targetDir = "Assets/Extracted";
    private bool importTextures = true;
    private bool buildPrefabs = true;
    private Vector2 scroll;
    private readonly List<string> log = new List<string>();

    [MenuItem("Tools/Clone App/Import Extracted Assets")]
    public static void Open()
    {
        GetWindow<ImportExtracted>("Import Extracted");
    }

    private void OnGUI()
    {
        EditorGUILayout.LabelField("clone-app extraction importer", EditorStyles.boldLabel);
        EditorGUILayout.HelpBox(
            "Select the game-assets/ folder produced by unity-extract.py.\n" +
            "Extracted art is reference material — check your rights before shipping it.",
            MessageType.Info);

        using (new EditorGUILayout.HorizontalScope())
        {
            sourceDir = EditorGUILayout.TextField("game-assets dir", sourceDir);
            if (GUILayout.Button("Browse", GUILayout.Width(70)))
            {
                var p = EditorUtility.OpenFolderPanel("Select game-assets", "", "");
                if (!string.IsNullOrEmpty(p)) sourceDir = p;
            }
        }
        targetDir = EditorGUILayout.TextField("Import into", targetDir);
        importTextures = EditorGUILayout.Toggle("Copy textures", importTextures);
        buildPrefabs = EditorGUILayout.Toggle("Build prefabs", buildPrefabs);

        GUI.enabled = Directory.Exists(sourceDir);
        if (GUILayout.Button("Import", GUILayout.Height(30))) Run();
        GUI.enabled = true;

        scroll = EditorGUILayout.BeginScrollView(scroll);
        foreach (var line in log) EditorGUILayout.LabelField(line);
        EditorGUILayout.EndScrollView();
    }

    private void Log(string m)
    {
        log.Add(m);
        Debug.Log("[ImportExtracted] " + m);
    }

    private void Run()
    {
        log.Clear();
        var entitiesDir = Path.Combine(sourceDir, "entities");
        if (!Directory.Exists(entitiesDir))
        {
            Log("ERROR: no entities/ under " + sourceDir);
            return;
        }

        Directory.CreateDirectory(targetDir);
        Directory.CreateDirectory(Path.Combine(targetDir, "Meshes"));
        Directory.CreateDirectory(Path.Combine(targetDir, "Textures"));
        Directory.CreateDirectory(Path.Combine(targetDir, "Materials"));
        Directory.CreateDirectory(Path.Combine(targetDir, "Prefabs"));

        var folders = Directory.GetDirectories(entitiesDir);
        int made = 0, skipped = 0;
        try
        {
            AssetDatabase.StartAssetEditing();
            for (int i = 0; i < folders.Length; i++)
            {
                var folder = folders[i];
                var jsonPath = Path.Combine(folder, "entity.json");
                if (!File.Exists(jsonPath)) { skipped++; continue; }
                EditorUtility.DisplayProgressBar("Importing", Path.GetFileName(folder),
                    (float)i / Mathf.Max(1, folders.Length));
                try
                {
                    if (CopyEntityAssets(folder)) made++;
                    else skipped++;
                }
                catch (Exception e)
                {
                    Log("WARN " + Path.GetFileName(folder) + ": " + e.Message);
                    skipped++;
                }
            }
        }
        finally
        {
            AssetDatabase.StopAssetEditing();
            EditorUtility.ClearProgressBar();
            AssetDatabase.Refresh();
        }

        if (buildPrefabs)
        {
            foreach (var folder in folders)
            {
                var jsonPath = Path.Combine(folder, "entity.json");
                if (!File.Exists(jsonPath)) continue;
                try { BuildPrefab(folder); }
                catch (Exception e) { Log("WARN prefab " + Path.GetFileName(folder) + ": " + e.Message); }
            }
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
        }

        Log($"copied {made} entities, skipped {skipped}. Prefabs in {targetDir}/Prefabs.");
    }

    // -- asset copy --------------------------------------------------------

    private bool CopyEntityAssets(string folder)
    {
        bool any = false;
        foreach (var obj in Directory.GetFiles(folder, "*.obj"))
        {
            CopyInto(obj, Path.Combine(targetDir, "Meshes"));
            any = true;
        }
        var broken = Path.Combine(folder, "broken");
        if (Directory.Exists(broken))
            foreach (var obj in Directory.GetFiles(broken, "*.obj"))
                CopyInto(obj, Path.Combine(targetDir, "Meshes"));
        foreach (var mtl in Directory.GetFiles(folder, "*.mtl"))
            CopyInto(mtl, Path.Combine(targetDir, "Meshes"));
        var tex = Path.Combine(folder, "textures");
        if (importTextures && Directory.Exists(tex))
            foreach (var png in Directory.GetFiles(tex, "*.png"))
                CopyInto(png, Path.Combine(targetDir, "Textures"));
        return any;
    }

    private void CopyInto(string src, string destDir)
    {
        var dest = Path.Combine(destDir, Path.GetFileName(src));
        if (!File.Exists(dest)) File.Copy(src, dest);
    }

    // -- prefab rebuild ----------------------------------------------------

    private void BuildPrefab(string folder)
    {
        var info = EntityInfo.Parse(File.ReadAllText(Path.Combine(folder, "entity.json")));
        if (info == null || string.IsNullOrEmpty(info.entity)) return;

        var go = new GameObject(info.entity);
        try
        {
            if (info.nodes.Count > 0)
                BuildFromNodes(info, go);
            else
                BuildFlat(info, go, folder);

            foreach (var c in info.colliders)
            {
                switch (c.type)
                {
                    case "BoxCollider":
                        var bc = go.AddComponent<BoxCollider>();
                        if (c.center != null) bc.center = c.center.Value;
                        if (c.size != null) bc.size = c.size.Value;
                        bc.isTrigger = c.isTrigger;
                        break;
                    case "SphereCollider":
                        var sc = go.AddComponent<SphereCollider>();
                        if (c.center != null) sc.center = c.center.Value;
                        if (c.radius.HasValue) sc.radius = c.radius.Value;
                        sc.isTrigger = c.isTrigger;
                        break;
                    case "CapsuleCollider":
                        var cc = go.AddComponent<CapsuleCollider>();
                        if (c.center != null) cc.center = c.center.Value;
                        if (c.radius.HasValue) cc.radius = c.radius.Value;
                        if (c.height.HasValue) cc.height = c.height.Value;
                        cc.isTrigger = c.isTrigger;
                        break;
                    case "MeshCollider":
                        var mc = go.AddComponent<MeshCollider>();
                        mc.convex = c.convex;
                        if (!string.IsNullOrEmpty(c.mesh))
                        {
                            var mp = Path.Combine(targetDir, "Meshes", c.mesh + ".obj").Replace("\\", "/");
                            mc.sharedMesh = AssetDatabase.LoadAssetAtPath<Mesh>(mp);
                        }
                        break;
                }
            }

            if (info.rigidbody != null)
            {
                var rb = go.AddComponent<Rigidbody>();
                if (info.rigidbody.mass.HasValue) rb.mass = info.rigidbody.mass.Value;
                if (info.rigidbody.drag.HasValue) rb.linearDamping = info.rigidbody.drag.Value;
                if (info.rigidbody.angularDrag.HasValue) rb.angularDamping = info.rigidbody.angularDrag.Value;
                rb.useGravity = info.rigidbody.useGravity;
                rb.isKinematic = info.rigidbody.isKinematic;
            }

            foreach (var j in info.joints)
            {
                // Connected bodies live in other prefabs; wire them up in the scene.
                if (j.type == "ConfigurableJoint") go.AddComponent<ConfigurableJoint>();
                else if (j.type == "HingeJoint") go.AddComponent<HingeJoint>();
                else if (j.type == "FixedJoint") go.AddComponent<FixedJoint>();
                else if (j.type == "SpringJoint") go.AddComponent<SpringJoint>();
            }

            var note = go.AddComponent<ExtractedEntityNote>();
            note.sourceEntity = info.entity;
            note.originalScripts = string.Join(", ", info.scripts);
            note.notes = "geometry_status=" + info.geometryStatus +
                         "; joints and connected bodies need manual wiring; " +
                         "MonoBehaviour field values were not recoverable.";

            var prefabPath = Path.Combine(targetDir, "Prefabs", info.entity + ".prefab").Replace("\\", "/");
            PrefabUtility.SaveAsPrefabAsset(go, prefabPath);
        }
        finally
        {
            DestroyImmediate(go);
        }
    }

    /// <summary>Rebuild the prefab's real hierarchy: one GameObject per extracted
    /// node, with its local transform, the mesh it actually carries and its
    /// materials in slot order. Fracture debris is parented under a disabled
    /// "Broken" root so the intact object is what you see.</summary>
    private void BuildFromNodes(EntityInfo info, GameObject root)
    {
        var made = new GameObject[info.nodes.Count];
        GameObject brokenRoot = null;

        for (int i = 0; i < info.nodes.Count; i++)
        {
            var n = info.nodes[i];
            GameObject g;
            if (i == 0) { g = root; }
            else
            {
                g = new GameObject(string.IsNullOrEmpty(n.name) ? "node" : n.name);
                var parent = (n.parent >= 0 && n.parent < made.Length && made[n.parent] != null)
                    ? made[n.parent].transform : root.transform;
                if (n.fracture)
                {
                    if (brokenRoot == null)
                    {
                        brokenRoot = new GameObject("Broken");
                        brokenRoot.transform.SetParent(root.transform, false);
                        brokenRoot.SetActive(false);
                    }
                    parent = brokenRoot.transform;
                }
                g.transform.SetParent(parent, false);
            }
            made[i] = g;

            if (n.localPosition != null) g.transform.localPosition = n.localPosition.Value;
            if (n.localRotation != null) g.transform.localRotation = n.localRotation.Value;
            if (n.localScale != null) g.transform.localScale = n.localScale.Value;
            if (i != 0 && !n.active) g.SetActive(false);

            if (!string.IsNullOrEmpty(n.meshFile))
            {
                var mp = Path.Combine(targetDir, "Meshes", n.meshFile).Replace("\\", "/");
                var mesh = AssetDatabase.LoadAssetAtPath<Mesh>(mp);
                if (mesh != null)
                {
                    g.AddComponent<MeshFilter>().sharedMesh = mesh;
                    var mr = g.AddComponent<MeshRenderer>();
                    // slot order matters: it maps to sub-mesh order
                    var mats = new List<Material>();
                    foreach (var mn in n.materials) mats.Add(ResolveNamedMaterial(info, mn));
                    if (mats.Count == 0) mats.Add(ResolveMaterial(info, null));
                    mr.sharedMaterials = mats.ToArray();
                }
            }
        }
    }

    private void BuildFlat(EntityInfo info, GameObject go, string folder)
    {
        foreach (var meshFile in info.wholeMeshFiles)
        {
            var assetPath = Path.Combine(targetDir, "Meshes", meshFile).Replace("\\", "/");
            var mesh = AssetDatabase.LoadAssetAtPath<Mesh>(assetPath);
            if (mesh == null) continue;
            var child = new GameObject(Path.GetFileNameWithoutExtension(meshFile));
            child.transform.SetParent(go.transform, false);
            child.AddComponent<MeshFilter>().sharedMesh = mesh;
            child.AddComponent<MeshRenderer>().sharedMaterial = ResolveMaterial(info, folder);
        }
    }

    /// <summary>Create (or fetch) one Unity material per extracted material, with
    /// ITS OWN textures — not the entity's first material applied to everything.</summary>
    private Material ResolveNamedMaterial(EntityInfo info, string matName)
    {
        if (string.IsNullOrEmpty(matName)) return ResolveMaterial(info, null);
        var path = Path.Combine(targetDir, "Materials", SafeName(matName) + ".mat").Replace("\\", "/");
        var existing = AssetDatabase.LoadAssetAtPath<Material>(path);
        if (existing != null) return existing;

        var shader = Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard");
        var mat = new Material(shader) { name = matName };

        MaterialInfo mi;
        if (info.materials.TryGetValue(matName, out mi))
        {
            foreach (var kv in mi.textureSlots)
            {
                var texPath = Path.Combine(targetDir, "Textures",
                    Path.GetFileName(kv.Value)).Replace("\\", "/");
                var tex = AssetDatabase.LoadAssetAtPath<Texture2D>(texPath);
                if (tex == null) continue;
                if (mat.HasProperty(kv.Key)) mat.SetTexture(kv.Key, tex);
                else if (mat.HasProperty("_BaseMap")) mat.SetTexture("_BaseMap", tex);
            }
            foreach (var kv in mi.colors) if (mat.HasProperty(kv.Key)) mat.SetColor(kv.Key, kv.Value);
            foreach (var kv in mi.floats) if (mat.HasProperty(kv.Key)) mat.SetFloat(kv.Key, kv.Value);
        }
        AssetDatabase.CreateAsset(mat, path);
        return mat;
    }

    private static string SafeName(string s)
    {
        foreach (var c in Path.GetInvalidFileNameChars()) s = s.Replace(c, '_');
        return s;
    }

    private Material ResolveMaterial(EntityInfo info, string folder)
    {
        if (string.IsNullOrEmpty(info.primaryMaterial)) return null;
        var path = Path.Combine(targetDir, "Materials", info.primaryMaterial + ".mat").Replace("\\", "/");
        var existing = AssetDatabase.LoadAssetAtPath<Material>(path);
        if (existing != null) return existing;

        var shader = Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard");
        var mat = new Material(shader) { name = info.primaryMaterial };
        foreach (var kv in info.primaryTextureSlots)
        {
            var texPath = Path.Combine(targetDir, "Textures",
                Path.GetFileName(kv.Value)).Replace("\\", "/");
            var tex = AssetDatabase.LoadAssetAtPath<Texture2D>(texPath);
            if (tex == null) continue;
            if (mat.HasProperty(kv.Key)) mat.SetTexture(kv.Key, tex);
            else if (mat.HasProperty("_BaseMap")) mat.SetTexture("_BaseMap", tex);
        }
        foreach (var kv in info.primaryColors)
            if (mat.HasProperty(kv.Key)) mat.SetColor(kv.Key, kv.Value);
        foreach (var kv in info.primaryFloats)
            if (mat.HasProperty(kv.Key)) mat.SetFloat(kv.Key, kv.Value);

        AssetDatabase.CreateAsset(mat, path);
        return mat;
    }

    // -- minimal JSON reader (no external dependency) ----------------------

    private class ColliderInfo
    {
        public string type, mesh;
        public bool isTrigger, convex;
        public Vector3? center, size;
        public float? radius, height;
    }

    private class JointInfo { public string type, connectedBody; }

    private class NodeInfo
    {
        public string name, meshFile;
        public int parent = -1;
        public bool active = true, fracture;
        public Vector3? localPosition, localScale;
        public Quaternion? localRotation;
        public List<string> materials = new List<string>();
    }

    private class MaterialInfo
    {
        public Dictionary<string, string> textureSlots = new Dictionary<string, string>();
        public Dictionary<string, Color> colors = new Dictionary<string, Color>();
        public Dictionary<string, float> floats = new Dictionary<string, float>();
    }

    private class RigidbodyInfo
    {
        public float? mass, drag, angularDrag;
        public bool useGravity, isKinematic;
    }

    private class EntityInfo
    {
        public string entity, geometryStatus, primaryMaterial;
        public List<string> wholeMeshFiles = new List<string>();
        public List<string> scripts = new List<string>();
        public List<ColliderInfo> colliders = new List<ColliderInfo>();
        public List<JointInfo> joints = new List<JointInfo>();
        public RigidbodyInfo rigidbody;
        public List<NodeInfo> nodes = new List<NodeInfo>();
        public Dictionary<string, MaterialInfo> materials = new Dictionary<string, MaterialInfo>();
        public Dictionary<string, string> primaryTextureSlots = new Dictionary<string, string>();
        public Dictionary<string, Color> primaryColors = new Dictionary<string, Color>();
        public Dictionary<string, float> primaryFloats = new Dictionary<string, float>();

        public static EntityInfo Parse(string json)
        {
            var node = MiniJson.Parse(json) as Dictionary<string, object>;
            if (node == null) return null;
            var e = new EntityInfo
            {
                entity = MiniJson.Str(node, "entity"),
                geometryStatus = MiniJson.Str(node, "geometry_status"),
            };
            foreach (var m in MiniJson.Arr(node, "whole_mesh_files"))
                e.wholeMeshFiles.Add(Convert.ToString(m));
            foreach (var s in MiniJson.Arr(node, "scripts"))
                e.scripts.Add(Convert.ToString(s));

            if (node.TryGetValue("rigidbody", out var rbo) && rbo is Dictionary<string, object> rb)
                e.rigidbody = new RigidbodyInfo
                {
                    mass = MiniJson.Flt(rb, "mass"),
                    drag = MiniJson.Flt(rb, "drag"),
                    angularDrag = MiniJson.Flt(rb, "angularDrag"),
                    useGravity = MiniJson.Bool(rb, "useGravity"),
                    isKinematic = MiniJson.Bool(rb, "isKinematic"),
                };

            foreach (var c in MiniJson.Arr(node, "colliders"))
            {
                if (!(c is Dictionary<string, object> cd)) continue;
                e.colliders.Add(new ColliderInfo
                {
                    type = MiniJson.Str(cd, "type"),
                    mesh = MiniJson.Str(cd, "mesh"),
                    isTrigger = MiniJson.Bool(cd, "isTrigger"),
                    convex = MiniJson.Bool(cd, "convex"),
                    center = MiniJson.Vec(cd, "center"),
                    size = MiniJson.Vec(cd, "size"),
                    radius = MiniJson.Flt(cd, "radius"),
                    height = MiniJson.Flt(cd, "height"),
                });
            }
            foreach (var j in MiniJson.Arr(node, "joints"))
            {
                if (!(j is Dictionary<string, object> jd)) continue;
                e.joints.Add(new JointInfo
                {
                    type = MiniJson.Str(jd, "type"),
                    connectedBody = MiniJson.Str(jd, "connectedBody"),
                });
            }
            if (node.TryGetValue("materials", out var mo) && mo is Dictionary<string, object> mats)
            {
                // every material, each with its OWN textures — assigning the first
                // material to every mesh is what made extracted objects look wrong
                foreach (var kv in mats)
                {
                    if (!(kv.Value is Dictionary<string, object> mdd)) continue;
                    var mi = new MaterialInfo();
                    if (mdd.TryGetValue("texture_slots", out var mts) && mts is Dictionary<string, object> tss)
                        foreach (var t in tss) mi.textureSlots[t.Key] = Convert.ToString(t.Value);
                    if (mdd.TryGetValue("colors", out var mcs) && mcs is Dictionary<string, object> cls)
                        foreach (var c in cls)
                        {
                            var v = MiniJson.Floats(c.Value);
                            if (v.Count >= 4) mi.colors[c.Key] = new Color(v[0], v[1], v[2], v[3]);
                        }
                    if (mdd.TryGetValue("floats", out var mfs) && mfs is Dictionary<string, object> fss)
                        foreach (var f in fss) mi.floats[f.Key] = Convert.ToSingle(f.Value);
                    e.materials[kv.Key] = mi;
                }
                foreach (var kv in mats)
                {
                    e.primaryMaterial = kv.Key;
                    if (!(kv.Value is Dictionary<string, object> md)) break;
                    if (md.TryGetValue("colors", out var co) && co is Dictionary<string, object> cols)
                        foreach (var c in cols)
                        {
                            var v = MiniJson.Floats(c.Value);
                            if (v.Count >= 4) e.primaryColors[c.Key] = new Color(v[0], v[1], v[2], v[3]);
                        }
                    if (md.TryGetValue("floats", out var fo) && fo is Dictionary<string, object> fls)
                        foreach (var f in fls)
                            e.primaryFloats[f.Key] = Convert.ToSingle(f.Value);
                    break;
                }
            }
            if (node.TryGetValue("texture_slots", out var to) && to is Dictionary<string, object> slots)
                foreach (var kv in slots)
                    e.primaryTextureSlots[kv.Key] = Convert.ToString(kv.Value);
            foreach (var nd in MiniJson.Arr(node, "nodes"))
            {
                if (!(nd is Dictionary<string, object> n)) continue;
                var ni = new NodeInfo
                {
                    name = MiniJson.Str(n, "name"),
                    meshFile = MiniJson.Str(n, "mesh_file"),
                    parent = n.TryGetValue("parent", out var pv) ? Convert.ToInt32(pv) : -1,
                    active = !n.TryGetValue("active", out var av) || Convert.ToBoolean(av),
                    fracture = n.TryGetValue("fracture", out var fv) && Convert.ToBoolean(fv),
                    localPosition = MiniJson.Vec(n, "localPosition"),
                    localScale = MiniJson.Vec(n, "localScale"),
                };
                var q = MiniJson.Floats(n.TryGetValue("localRotation", out var rv) ? rv : null);
                if (q.Count >= 4) ni.localRotation = new Quaternion(q[0], q[1], q[2], q[3]);
                foreach (var m in MiniJson.Arr(n, "materials"))
                    ni.materials.Add(Convert.ToString(m));
                e.nodes.Add(ni);
            }
            return e;
        }
    }

    // Tiny JSON parser — Unity's JsonUtility cannot read the nested, dynamic
    // shape of entity.json, and pulling in a package for one importer is silly.
    private static class MiniJson
    {
        public static object Parse(string s)
        {
            int i = 0;
            return ParseValue(s, ref i);
        }

        public static string Str(Dictionary<string, object> d, string k)
            => d != null && d.TryGetValue(k, out var v) && v != null ? Convert.ToString(v) : null;

        public static bool Bool(Dictionary<string, object> d, string k)
            => d != null && d.TryGetValue(k, out var v) && v is bool b && b;

        public static float? Flt(Dictionary<string, object> d, string k)
        {
            if (d == null || !d.TryGetValue(k, out var v) || v == null) return null;
            try { return Convert.ToSingle(v); } catch { return null; }
        }

        public static List<object> Arr(Dictionary<string, object> d, string k)
            => d != null && d.TryGetValue(k, out var v) && v is List<object> l ? l : new List<object>();

        public static List<float> Floats(object v)
        {
            var outv = new List<float>();
            if (v is List<object> l)
                foreach (var x in l) { try { outv.Add(Convert.ToSingle(x)); } catch { } }
            return outv;
        }

        public static Vector3? Vec(Dictionary<string, object> d, string k)
        {
            if (d == null || !d.TryGetValue(k, out var v)) return null;
            var f = Floats(v);
            return f.Count >= 3 ? new Vector3(f[0], f[1], f[2]) : (Vector3?)null;
        }

        private static object ParseValue(string s, ref int i)
        {
            SkipWs(s, ref i);
            if (i >= s.Length) return null;
            switch (s[i])
            {
                case '{': return ParseObject(s, ref i);
                case '[': return ParseArray(s, ref i);
                case '"': return ParseString(s, ref i);
                case 't': i += 4; return true;
                case 'f': i += 5; return false;
                case 'n': i += 4; return null;
                default: return ParseNumber(s, ref i);
            }
        }

        private static Dictionary<string, object> ParseObject(string s, ref int i)
        {
            var d = new Dictionary<string, object>();
            i++; // {
            while (i < s.Length)
            {
                SkipWs(s, ref i);
                if (i < s.Length && s[i] == '}') { i++; break; }
                var key = ParseString(s, ref i);
                SkipWs(s, ref i);
                if (i < s.Length && s[i] == ':') i++;
                d[key] = ParseValue(s, ref i);
                SkipWs(s, ref i);
                if (i < s.Length && s[i] == ',') i++;
            }
            return d;
        }

        private static List<object> ParseArray(string s, ref int i)
        {
            var l = new List<object>();
            i++; // [
            while (i < s.Length)
            {
                SkipWs(s, ref i);
                if (i < s.Length && s[i] == ']') { i++; break; }
                l.Add(ParseValue(s, ref i));
                SkipWs(s, ref i);
                if (i < s.Length && s[i] == ',') i++;
            }
            return l;
        }

        private static string ParseString(string s, ref int i)
        {
            SkipWs(s, ref i);
            if (i >= s.Length || s[i] != '"') return "";
            i++;
            var sb = new System.Text.StringBuilder();
            while (i < s.Length && s[i] != '"')
            {
                if (s[i] == '\\' && i + 1 < s.Length)
                {
                    i++;
                    switch (s[i])
                    {
                        case 'n': sb.Append('\n'); break;
                        case 't': sb.Append('\t'); break;
                        case 'r': sb.Append('\r'); break;
                        case 'u':
                            sb.Append((char)Convert.ToInt32(s.Substring(i + 1, 4), 16));
                            i += 4; break;
                        default: sb.Append(s[i]); break;
                    }
                }
                else sb.Append(s[i]);
                i++;
            }
            i++;
            return sb.ToString();
        }

        private static object ParseNumber(string s, ref int i)
        {
            int start = i;
            while (i < s.Length && (char.IsDigit(s[i]) || s[i] == '-' || s[i] == '+' ||
                                    s[i] == '.' || s[i] == 'e' || s[i] == 'E')) i++;
            var t = s.Substring(start, i - start);
            if (double.TryParse(t, System.Globalization.NumberStyles.Float,
                                System.Globalization.CultureInfo.InvariantCulture, out var d))
                return d;
            return 0d;
        }

        private static void SkipWs(string s, ref int i)
        {
            while (i < s.Length && char.IsWhiteSpace(s[i])) i++;
        }
    }
}
#endif
