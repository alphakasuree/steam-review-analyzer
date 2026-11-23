using System;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Linq;
using System.Collections.Generic;
using System.Reflection;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using System.Web.Script.Serialization;

public class LinearModel {
    public string[] vocab, labels;
    public double[] idf,bias;
    public double[][] weights;
    public double threshold;
    public Dictionary<string,string> terms,aliases;
}
public class ReviewPage {
    public PageBody response;
    public class PageBody {public SteamReview[] reviews; public string cursor;}
    public class SteamReview {public string recommendationid,review,language;}
}
public class LiveReviews {
    readonly LinearModel model;
    readonly Dictionary<string,int> index;
    static readonly HttpClient client=new HttpClient { Timeout=TimeSpan.FromSeconds(25) };
    static readonly JavaScriptSerializer json=new JavaScriptSerializer{MaxJsonLength=int.MaxValue};
    public LiveReviews(){
        using(var reader=new StreamReader(Assembly.GetExecutingAssembly().GetManifestResourceStream("classifier.json")))
            model=json.Deserialize<LinearModel>(reader.ReadToEnd());
        index=Enumerable.Range(0,model.vocab.Length).ToDictionary(i=>model.vocab[i],i=>i);
    }
    public static uint AppId(string input){
        uint id;
        if(uint.TryParse(input.Trim(),out id)&&id>0)return id;
        Uri url;
        if(Uri.TryCreate(input.Trim(),UriKind.Absolute,out url) && (url.Scheme=="https"||url.Scheme=="http") && url.Host=="store.steampowered.com"){
            var match=Regex.Match(url.AbsolutePath,@"^/app/(\d+)(?:/|$)");
            if(match.Success && uint.TryParse(match.Groups[1].Value,out id) && id>0)return id;
        }
        throw new FormatException("Steam 게임 상점 주소 또는 게임 번호를 입력하세요.");
    }
    public IEnumerable<object[]> Predict(int id,string review){
        foreach(var raw in Regex.Split(review,@"[\n.!?。]+|\s+(?:근데|그런데|하지만)\s+")){
            string s=raw.Trim();
            if(!Regex.IsMatch(s,"[가-힣]"))continue;
            string text=Regex.Replace(s.ToLowerInvariant(),@"\s\s+"," ");
            var features=new Dictionary<int,double>();
            for(int k=2;k<=4;k++)for(int i=0;i+k<=text.Length;i++){
                int j; if(!index.TryGetValue(text.Substring(i,k),out j))continue;
                double count;features.TryGetValue(j,out count);features[j]=count+1;
            }
            foreach(int j in features.Keys.ToArray())features[j]=(1+Math.Log(features[j]))*model.idf[j];
            double norm=Math.Sqrt(features.Values.Sum(value=>value*value));
            for(int j=0;j<model.labels.Length;j++){
                double score=model.bias[j];
                if(norm>0 && model.weights[j].Length>0)foreach(var pair in features)score+=model.weights[j][pair.Key]*pair.Value/norm;
                if(score<Math.Log(model.threshold/(1-model.threshold)))continue;
                var cat=model.labels[j].Substring(0,model.labels[j].LastIndexOf('·'));
                var words=model.terms[cat].Split(' ').Where(w=>Regex.IsMatch(s,model.aliases.ContainsKey(w)?model.aliases[w]:w,RegexOptions.IgnoreCase)).ToArray();
                yield return new object[]{id,s,j,words.Length>0?words:new[]{"그 외 표현"}};
            }
        }
    }
    public async Task<Data> Fetch(uint app,int limit,IProgress<string> progress){
        ServicePointManager.SecurityProtocol |= SecurityProtocolType.Tls12;
        var reviews=new List<string>();var seen=new HashSet<string>();var cursors=new HashSet<string>();
        var evidence=new List<object[]>();string cursor="*";
        while(reviews.Count<limit && cursors.Add(cursor)){
            var query=new {appid=app,languages=new[]{"koreana"},filter=1,review_type=0,purchase_type=1,num_per_page=Math.Min(100,limit-reviews.Count),cursor=cursor};
            string url="https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/?input_json="+Uri.EscapeDataString(json.Serialize(query));
            using(var result=await client.GetAsync(url).ConfigureAwait(false)){
                if((int)result.StatusCode==429)throw new IOException("Steam 요청 한도에 도달했어요. 잠시 뒤 다시 시도하세요.");
                result.EnsureSuccessStatusCode();
                var body=json.Deserialize<ReviewPage>(await result.Content.ReadAsStringAsync().ConfigureAwait(false)).response;
                if(body==null)throw new IOException("Steam 응답을 확인할 수 없습니다.");
                if(body.reviews==null||body.reviews.Length==0)break;
                foreach(var r in body.reviews){
                    if(r.language!="koreana"||string.IsNullOrWhiteSpace(r.review)||!seen.Add(r.recommendationid))continue;
                    evidence.AddRange(Predict(reviews.Count,r.review));reviews.Add(r.review);
                }
                if(progress!=null)progress.Report("한국어 리뷰 "+reviews.Count+"개 분석");
                cursor=body.cursor;if(string.IsNullOrEmpty(cursor)||reviews.Count>=limit)break;
            }
            await Task.Delay(1500).ConfigureAwait(false);
        }
        if(reviews.Count==0)throw new IOException("이 게임에서 분석할 한국어 리뷰를 찾지 못했어요.");
        return new Data{games=Enumerable.Repeat("Steam 게임 "+app,reviews.Count).ToArray(),reviews=reviews.ToArray(),labels=model.labels,evidence=evidence.ToArray()};
    }
}
