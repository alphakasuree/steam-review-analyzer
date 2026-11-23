using System;
using System.IO;
using System.Drawing;
using System.Linq;
using System.Collections.Generic;
using System.Reflection;
using System.Windows.Forms;
using System.Web.Script.Serialization;

public class Data {
    public string[] games, reviews, labels;
    public object[][] evidence;
}
public class ReviewWindow : Form {
    readonly Data data;
    ComboBox game = new ComboBox(), category = new ComboBox();
    ListBox positive = new ListBox(), negative = new ListBox(), excerpts = new ListBox();
    TextBox original = new TextBox();
    Label status = new Label();
    bool refreshing;
    class Keyword {
        public string Name;
        public Dictionary<int,string> Items = new Dictionary<int,string>();
        public override string ToString(){ return Name + "   (" + Items.Count + ")"; }
    }
    class Quote {
        public int Id;
        public string Text;
        public override string ToString(){return Text;}
    }
    static Control Box(string title, Control control){
        var box=new GroupBox {Text=title,Dock=DockStyle.Fill,Padding=new Padding(10)};
        control.Dock=DockStyle.Fill;
        box.Controls.Add(control); return box;
    }
    public ReviewWindow(){
        using(var reader=new StreamReader(Assembly.GetExecutingAssembly().GetManifestResourceStream("reviews.json"))){
            data=new JavaScriptSerializer {MaxJsonLength=int.MaxValue}.Deserialize<Data>(reader.ReadToEnd());
        }
        Text="스팀 리뷰 분석"; ClientSize=new Size(960,700); MinimumSize=new Size(680,560);
        Font=new Font("Malgun Gothic",10); StartPosition=FormStartPosition.CenterScreen;
        var layout=new TableLayoutPanel {Dock=DockStyle.Fill,ColumnCount=2,RowCount=6,Padding=new Padding(16)};
        for(int i=0;i<2;i++)layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,50));
        foreach(float height in new float[]{38,68,32})layout.RowStyles.Add(new RowStyle(SizeType.Absolute,height));
        foreach(float percent in new float[]{30,32,38})layout.RowStyles.Add(new RowStyle(SizeType.Percent,percent));
        Controls.Add(layout);
        var heading=new Label {Text="스팀 리뷰 분석",Font=new Font(Font.FontFamily,17,FontStyle.Bold),Dock=DockStyle.Fill};
        layout.Controls.Add(heading,0,0); layout.SetColumnSpan(heading,2);
        game.DropDownStyle=category.DropDownStyle=ComboBoxStyle.DropDownList;
        layout.Controls.Add(Box("게임",game),0,1);layout.Controls.Add(Box("카테고리",category),1,1);
        status.Dock=DockStyle.Fill; layout.Controls.Add(status,0,2);layout.SetColumnSpan(status,2);
        layout.Controls.Add(Box("장점 키워드 · 리뷰 수",positive),0,3);
        layout.Controls.Add(Box("단점 키워드 · 리뷰 수",negative),1,3);
        excerpts.HorizontalScrollbar=true;
        var quotes=Box("근거 구절",excerpts);layout.Controls.Add(quotes,0,4);layout.SetColumnSpan(quotes,2);
        original.Multiline=true;original.ReadOnly=true;original.ScrollBars=ScrollBars.Vertical;original.BackColor=Color.White;
        var full=Box("선택한 리뷰 원문",original);layout.Controls.Add(full,0,5);layout.SetColumnSpan(full,2);
        game.Items.AddRange(data.games.Distinct().ToArray());
        category.Items.AddRange(data.labels.Select(x=>x.Substring(0,x.LastIndexOf('·'))).Distinct().ToArray());
        game.SelectedIndex=category.SelectedIndex=0;
        game.SelectedIndexChanged+=(s,e)=>Filter();category.SelectedIndexChanged+=(s,e)=>Filter();
        positive.SelectedIndexChanged+=(s,e)=>Pick(positive,negative);negative.SelectedIndexChanged+=(s,e)=>Pick(negative,positive);
        excerpts.SelectedIndexChanged+=(s,e)=>{var q=excerpts.SelectedItem as Quote;original.Text=q==null?"":data.reviews[q.Id].Replace("\r\n","\n").Replace("\n",Environment.NewLine);};
        Filter();
    }
    void Filter(){
        refreshing=true;
        string g=(string)game.SelectedItem,c=(string)category.SelectedItem;
        status.Text=String.Format("분석 대상 {0:N0}개 리뷰   ·   AI 예측   ·   키워드를 선택하세요",data.games.Count(x=>x==g));
        foreach(var list in new[]{positive,negative}){
            var buckets=new Dictionary<string,Keyword>();
            string tag=c+"·"+(list==positive?"긍정":"부정");
            foreach(var row in data.evidence){
                int id=Convert.ToInt32(row[0]);
                if(data.games[id]!=g || data.labels[Convert.ToInt32(row[2])]!=tag)continue;
                foreach(string key in (System.Collections.IEnumerable)row[3]){
                    if(!buckets.ContainsKey(key))buckets[key]=new Keyword{Name=key};
                    buckets[key].Items[id]=(string)row[1];
                }
            }
            list.Items.Clear();
            foreach(var k in buckets.Values.OrderBy(x=>x.Name=="그 외 표현").ThenByDescending(x=>x.Items.Count).Take(5))list.Items.Add(k);
            list.Enabled=list.Items.Count>0;
            if(!list.Enabled)list.Items.Add("해당 의견 없음");
        }
        excerpts.Items.Clear();original.Clear();refreshing=false;
        if(positive.Enabled)positive.SelectedIndex=0;else if(negative.Enabled)negative.SelectedIndex=0;
    }
    void Pick(ListBox list,ListBox other){
        var key=list.SelectedItem as Keyword;
        if(refreshing||key==null)return;
        other.ClearSelected();excerpts.BeginUpdate();excerpts.Items.Clear();
        foreach(var item in key.Items)excerpts.Items.Add(new Quote{Id=item.Key,Text=item.Value});
        excerpts.EndUpdate();excerpts.SelectedIndex=0;
    }
    public void Check(){
        for(int g=0;g<game.Items.Count;g++)for(int c=0;c<category.Items.Count;c++){
            game.SelectedIndex=g;category.SelectedIndex=c;
            foreach(var list in new[]{positive,negative})if(list.Enabled)for(int i=0;i<list.Items.Count;i++){
                list.SelectedIndex=i;
                if(excerpts.Items.Count==0||original.Text.Length==0)throw new Exception("Missing evidence");
            }
        }
    }
    [STAThread] public static int Main(string[] args){
        Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
        using(var window=new ReviewWindow()){
            if(args.Contains("--check"))window.Check();else Application.Run(window);
        }
        return 0;
    }
}
